"""Failure provenance and feedback isolation; model fixtures are not quality tests."""

import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from app.adapters.retrieval.knowledge import import_knowledge
from app.adapters.retrieval.rule_routing import operation_for, retrieve_rule_roles
from app.contracts.stages import RuleResponse
from app.core.db import engine
from app.domain.audit import AuditError
from app.persistence.stage_models import StageRun
from app.services.rule_drafts import confirmed_evidence
from app.services.rules import RuleService
from sqlmodel import Session


def make_stage(context, flags):
    with Session(engine) as db:
        row = StageRun(
            audit_id=context["run_id"],
            kind="rule",
            prompt_version="3",
            inputs={
                "requirement": "Generate Python eval detector with actual dataflow",
                "purpose": "vulnerability_detector",
                "strategy": "new_query",
            },
            model_config_snapshot={"rule_experiment": flags},
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return str(row.id)


def draft(identifier):
    return RuleResponse(
        purpose="vulnerability_detector",
        title="eval detector",
        strategy="new_query",
        coverage_analysis="This draft requires independent source/sink verification.",
        query='import python\nfrom Call c select c, "candidate"',
        knowledge_ids=[identifier],
        positive={
            "files": {"a.py": "eval(input())\n"},
            "expected": [{"file": "a.py", "line": 1}],
        },
        negative={"files": {"a.py": "int(input())\n"}, "expected": []},
    )


@pytest.mark.parametrize("full", [True, False])
def test_metadata_failure_retained_and_candidate_feedback(
    pipeline_context, monkeypatch, full
):
    stage = make_stage(pipeline_context, {"full_feedback": full})
    identifier = uuid4()
    payloads = []

    class Provider:
        def __init__(self):
            self.usage = {}

        model = "fixture-only"

        def generate(self, purpose, payload, schema):
            payloads.append(json.loads(json.dumps(payload)))
            return draft(identifier)

    service = RuleService(stage, Provider())
    with pytest.raises(AuditError, match="两次"):
        service.generate({"knowledge": [{"id": str(identifier)}], "target": None})
    directory = service.directory
    assert (directory / "draft-0/candidate.json").exists()
    assert (
        json.loads((directory / "draft-0/diagnostic.json").read_text())["code"]
        == "contract_error"
    )
    assert (directory / "draft-1/candidate.json").exists()
    assert ("previous_candidate" in payloads[1]) is full
    if full:
        assert payloads[1]["previous_candidate"]["query"] == draft(identifier).query
        assert "缺少 @id" in payloads[1]["compiler_feedback"]["message"]


def test_routing_excludes_wrong_operation(pipeline_context):
    owner = pipeline_context["owner"]
    for title, content in [
        ("correct", "CodeInjectionQuery exact flow declaration"),
        ("wrong", "SqlInjectionQuery eval SQL XSS unrelated API"),
        ("conversion declarations", "class Node conversion declaration API"),
    ]:
        import_knowledge(
            owner, title, title, "python", content, {"api_version": "test-routed"}
        )
    rows = retrieve_rule_roles(owner, "python", "Python eval detector", "test-routed")
    assert any("query" in row["roles"] for row in rows)
    assert not any(row["title"] == "wrong" for row in rows)
    assert any("types" in row["roles"] for row in rows)


def test_candidate_evidence_cannot_cross_audit(pipeline_context):
    candidate = SimpleNamespace(evidence_ids=[str(uuid4())])
    audit = SimpleNamespace(id=pipeline_context["run_id"], snapshot_hash="snapshot")
    with pytest.raises(AuditError, match="证据缺失"):
        confirmed_evidence(candidate, audit)
    with pytest.raises(AuditError, match="实际证据"):
        confirmed_evidence(SimpleNamespace(evidence_ids=[]), audit)


def test_ambiguous_operation_rejected():
    with pytest.raises(AuditError, match="唯一"):
        operation_for("Generate eval and SQL detectors")


def test_framework_spec_rejects_unretrieved_sink_symbols():
    from app.adapters.codeql.model_spec import generate_framework_spec

    identifier = uuid4()

    class Provider:
        def generate(self, purpose, payload, schema):
            return schema.model_validate(
                {
                    "language": "python",
                    "operation": "eval",
                    "purpose": "vulnerability_detector",
                    "title": "grounded sink",
                    "coverage_analysis": "An imported API needs an independently checked model.",
                    "sinks": [
                        {
                            "module": "unretrieved",
                            "member": "execute",
                            "argument": 0,
                            "evidence_id": str(identifier),
                        }
                    ],
                    "knowledge_ids": [str(identifier)],
                    "positive": {
                        "files": {"a.py": "pass\n"},
                        "expected": [{"file": "a.py", "line": 1}],
                    },
                    "negative": {"files": {"b.py": "pass\n"}, "expected": []},
                }
            )

    with pytest.raises(AuditError, match="实际检索证据"):
        generate_framework_spec(
            Provider(),
            {
                "language": "python",
                "purpose": "vulnerability_detector",
                "knowledge": [{"id": str(identifier), "content": "other.execute API"}],
            },
        )


def test_model_spec_cannot_inject_ql():
    from app.adapters.codeql.model_spec import SinkSpec
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        SinkSpec(
            module='mod"); select 1 //',
            member="execute",
            argument=0,
            evidence_id=uuid4(),
        )
    with pytest.raises(ValidationError):
        SinkSpec(module="mod", member="execute", argument=99, evidence_id=uuid4())


def test_benchmark_labels_align_with_source():
    from scripts.benchmarks.framework_ablation import fixture

    for index in range(3):
        data, _ = fixture(index)
        for expected in data["fixtures"]["positive"]["expected"]:
            lines = data["fixtures"]["positive"]["files"][expected["file"]].splitlines()
            assert "# target" in lines[expected["line"] - 1]


def test_development_execution_enters_bounded_feedback(pipeline_context, monkeypatch):
    import app.services.rules as module

    stage = make_stage(pipeline_context, {"full_feedback": True, "execute_dev": True})
    identifier = uuid4()
    payloads = []

    class Provider:
        model = "fixture-only"

        def __init__(self):
            self.usage = {}

        def generate(self, purpose, payload, schema):
            payloads.append(json.loads(json.dumps(payload)))
            response = draft(identifier)
            response.query = """/** @id audit/dev-feedback
 * @name dev feedback
 * @description test candidate
 * @kind problem
 * @problem.severity warning
 * @precision low
 */
import python
from Call c select c, "candidate"
"""
            return response

    monkeypatch.setattr(module, "compile_query", lambda *args: None)
    outcomes = iter(
        [
            {
                "status": "failed",
                "tests": {"positive": {"expected": [["a.py", 1]], "actual": []}},
            },
            {"status": "passed", "tests": {}},
        ]
    )
    monkeypatch.setattr(module, "validate_fixtures", lambda *args: next(outcomes))
    result = RuleService(stage, Provider()).generate(
        {"knowledge": [{"id": str(identifier)}], "target": None}
    )
    assert result["rule_id"]
    assert len(payloads) == 2
    assert payloads[1]["development_feedback"]["tests"]["positive"]["actual"] == []
    assert (
        payloads[1]["previous_candidate"]["positive"]["files"]["a.py"]
        == "eval(input())\n"
    )
