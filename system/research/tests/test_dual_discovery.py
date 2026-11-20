"""Exercise native dual discovery, its immutable member indexes and failures."""

import json
from threading import Event
from types import SimpleNamespace

import pytest
from discovery_cases import make_scan
from openai.types.chat import ChatCompletion
from semflow_contracts.bundles import AssessmentBundle, CandidateBundle, EvidenceBundle
from semflow_contracts.errors import ResearchError
from semflow_contracts.runs import validate_spec
from semflow_research.public.discovery import execute
from semflow_research.public.runtime import prepare
from semflow_research.runtime.bundle_reader import authorize_artifacts, resolve_bundle
from semflow_research.runtime.children import child_id
from semflow_research.runtime.ledger import input_artifacts
from semflow_research.state.models import Candidate


def make_dual(case, settings, *, required=("scan", "scout"), max_calls=8, review=True):
    scanned = make_scan(case, settings)
    value = scanned.model_dump(mode="json")
    prompts = []
    for role, version in (("scout", "1"), ("review", "4")):
        content = case.artifacts.commit(
            ("Scripted " + role + "; preserve unresolved premises.").encode(),
            kind="prompt",
            schema_version="prompt/1",
        )
        prompts.append(
            {
                "role": role,
                "version": version,
                "template_id": role,
                "sha256": content.sha256,
                "content": content.model_dump(mode="json"),
            }
        )
    value.update(
        operation="discover",
        prompts=prompts,
        model={
            "provider": "scripted-test",
            "model": "scripted",
            "endpoint_profile": "scripted",
            "output_schema_version": "1",
            "output_tokens": 2000,
        },
        inputs={
            "scan": value["inputs"],
            "scout": {
                "window_policy": {
                    "version": "1",
                    "max_windows": 1,
                    "max_steps_per_window": 1,
                    "max_calls": 1,
                }
            },
            "scout_method_version": "1",
            "review_method_version": "4",
            "required_branches": list(required),
            "review": {
                "version": "1",
                "batch_size": 2,
                "max_batches": 0,
                "supplement_insufficient": False,
                "max_steps": 1,
                "max_context_chars": 40000,
            }
            if review
            else None,
        },
    )
    value["implementation"]["method_version"] = "1"
    value["policy"].update(
        max_calls=max_calls, max_tokens=200000, max_seconds=60, max_context_chars=40000
    )
    return validate_spec(value)


@pytest.fixture
def model(monkeypatch):
    calls = []

    def create(**kwargs):
        payload = json.loads(kwargs["messages"][-1]["content"])[
            "untrusted_analysis_material"
        ]
        calls.append(payload)
        if "unit" in payload:
            source = payload["evidence"][0]
            body = {
                "action": "final",
                "scope_summary": "Inspected independent source window",
                "findings": [
                    {
                        "title": "Independent eval hypothesis",
                        "weakness": "CWE-95",
                        "primary_location": {"file": "app.py", "line": 1},
                        "security_condition": "Untrusted input may reach dynamic execution",
                        "observation": "eval receives a value from input",
                        "missing_premises": ["Caller trust is unknown"],
                        "evidence_ids": [source["id"]],
                    }
                ],
            }
        else:
            body = {
                "action": "final",
                "summary": "All supplied hypotheses were inspected; caller trust remains unknown",
                "candidate_assessments": [
                    {
                        "candidate_id": target["candidate_id"],
                        "assessment": "insufficient",
                        "weakness": "CWE-95",
                        "reason": "The supplied source does not establish the caller trust boundary",
                        "evidence_ids": target["evidence_ids"],
                        "missing_premises": ["Caller trust is unknown"],
                    }
                    for target in payload["targets"]
                ],
                "new_findings": [],
                "anchor_assessments": [],
                "root_relations": [],
            }
        return ChatCompletion(
            id="scripted",
            created=0,
            model="scripted",
            object="chat.completion",
            choices=[
                {
                    "index": 0,
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": json.dumps(body)},
                }
            ],
            usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        )

    def factory(**kwargs):
        return SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create)),
            base_url="http://scripted.invalid/v1",
        )

    monkeypatch.setattr("semflow_research.adapters.ai.provider.OpenAI", factory)
    return calls


def read_output(context, result):
    return authorize_artifacts(context, input_artifacts(result))


def test_dual_branches_run_independently_and_keep_member_producer_ids(
    research_case, settings, scanner, model, monkeypatch
):
    from semflow_research.adapters.ai.provider import CompatibleModel
    from semflow_research.adapters.codeql.scanner import CodeQLScanner

    scan_entered, scout_called = Event(), Event()
    original_create = CodeQLScanner.create_database
    original_generate = CompatibleModel.generate

    def create(self, source, output, log, plan):
        scan_entered.set()
        assert scout_called.wait(5), "Scout must run while static scan is still pending"
        return original_create(self, source, output, log, plan)

    def generate(self, purpose, payload, schema):
        if purpose == "scout":
            assert scan_entered.wait(5)
            scout_called.set()
            assert self.context.records.list(Candidate) == []
            assert (
                self.context.source_records.get(
                    self.context.spec.source.snapshot_id
                ).findings
                == []
            )
        return original_generate(self, purpose, payload, schema)

    monkeypatch.setattr(CodeQLScanner, "create_database", create)
    monkeypatch.setattr(CompatibleModel, "generate", generate)
    spec = make_dual(research_case, settings)
    context = prepare(spec, root=research_case.ledger.root, settings=settings)
    result = execute(spec, context)
    assert result.execution_status == "completed", result.failure
    assert result.completeness.status == "full"
    assert [branch.branch for branch in result.result.branches] == [
        "scan",
        "scout",
        "review",
    ]
    assert all(branch.result_manifest is not None for branch in result.result.branches)
    assert result.usage.calls == 2 and result.usage.input_tokens == 200
    received = read_output(context, result)
    received, candidates = resolve_bundle(
        received, result.result.candidates, CandidateBundle
    )
    received, evidence = resolve_bundle(
        received, result.result.evidence, EvidenceBundle
    )
    received, assessments = resolve_bundle(
        received, result.result.assessments, AssessmentBundle
    )
    review_id = child_id(spec.execution_id, "review")
    assert {row.execution_id for row in candidates.records} == {review_id}
    assert {row.derived_from.execution_id for row in candidates.records} == {
        child_id(spec.execution_id, "scan"),
        child_id(spec.execution_id, "scout"),
    }
    assert len(candidates.records) == len(assessments.records) == 2
    assert all(
        row.conclusion == "insufficient" and row.unknown_premises
        for row in assessments.records
    )
    assert {row.execution_id for row in evidence.records} == {
        child_id(spec.execution_id, role) for role in ("scan", "scout", "review")
    }
    for row in evidence.records:
        if row.kind == "code":
            received.source.validate(row)
    assert "py/code-injection" not in json.dumps(
        next(payload for payload in model if "unit" in payload)
    )
    for branch in result.result.branches:
        saved = context.executions.inspect(branch.execution_id)
        assert saved.usage.calls == (0 if branch.branch == "scan" else 1)
    assert execute(spec, context) == result
    assert len(model) == 2 and scanner == ["database", "analyze"]
    assert context.executions.inspect(spec.execution_id) == result


def test_required_scan_failure_keeps_scout_and_review_outputs(
    research_case, settings, scanner, model, monkeypatch
):
    from semflow_research.adapters.codeql.scanner import CodeQLScanner

    def failed(*args):
        raise ResearchError("tool_failed", "Scripted CodeQL extraction failure")

    monkeypatch.setattr(CodeQLScanner, "create_database", failed)
    spec = make_dual(research_case, settings)
    context = prepare(spec, root=research_case.ledger.root, settings=settings)
    result = execute(spec, context)
    assert result.execution_status == "failed" and result.failure.code == "tool_failed"
    assert result.completeness.status == "partial" and result.result is not None
    assert [(branch.branch, branch.status) for branch in result.result.branches] == [
        ("scan", "failed"),
        ("scout", "completed"),
        ("review", "completed"),
    ]
    received = read_output(context, result)
    _, candidates = resolve_bundle(received, result.result.candidates, CandidateBundle)
    assert len(candidates.records) == 1 and candidates.records[
        0
    ].derived_from.execution_id == child_id(spec.execution_id, "scout")
    assert any("scan" in reason for reason in result.completeness.reasons)


def test_optional_scan_failure_is_explicit_partial_success(
    research_case, settings, scanner, model, monkeypatch
):
    from semflow_research.adapters.codeql.scanner import CodeQLScanner

    monkeypatch.setattr(
        CodeQLScanner,
        "create_database",
        lambda *args: (_ for _ in ()).throw(
            ResearchError("tool_failed", "Scripted failure")
        ),
    )
    spec = make_dual(research_case, settings, required=("scout",))
    context = prepare(spec, root=research_case.ledger.root, settings=settings)
    result = execute(spec, context)
    assert (
        result.execution_status == "completed"
        and result.completeness.status == "partial"
    )
    assert result.result.branches[0].failure.code == "tool_failed"


def test_child_review_cannot_reset_parent_model_budget(
    research_case, settings, scanner, model
):
    spec = make_dual(research_case, settings, max_calls=1)
    context = prepare(spec, root=research_case.ledger.root, settings=settings)
    result = execute(spec, context)
    assert result.completeness.status == "partial"
    assert result.usage.calls == len(model) == 1
    review = context.executions.inspect(child_id(spec.execution_id, "review"))
    assert review.result.coverage.status == "partial"
    assert review.result.coverage.unreviewed_candidate_refs
    assert (
        any("budget" in reason.lower() for reason in result.completeness.reasons)
        or result.result.coverage.unreviewed_candidate_refs
    )


def test_evidence_scheduler_uses_reserved_model_call_for_review(
    research_case, settings, scanner, model
):
    original = make_dual(research_case, settings, required=("scan",), max_calls=1)
    value = original.model_dump(mode="json")
    value["inputs"]["review"]["scheduler"] = "evidence_v3"
    spec = validate_spec(value)
    context = prepare(spec, root=research_case.ledger.root, settings=settings)
    result = execute(spec, context)
    assert result.execution_status == "completed"
    assert result.usage.calls == len(model) == 1
    assert len(model[0]["targets"]) == 1
    assert model[0]["targets"][0]["evidence_ids"]
    review = context.executions.inspect(child_id(spec.execution_id, "review"))
    assert review is not None and review.execution_status == "completed"
    view = read_output(context, review)
    _, assessments = resolve_bundle(view, review.result.assessments, AssessmentBundle)
    assert [r.conclusion for r in assessments.records] == ["insufficient"]


def test_unavailable_alert_does_not_stop_independent_review(
    research_case, settings, scanner, model, monkeypatch
):
    from copy import deepcopy

    from semflow_research.adapters.codeql.scanner import CodeQLScanner
    from semflow_research.domain.errors import AuditError
    from semflow_research.evidence.evidence import EvidenceService
    from semflow_research.runtime.sources import capture

    case = research_case
    (case.source / "unreadable.py").write_text("value = 1\n", encoding="utf-8")
    snapshot = capture(case.source, artifacts=case.artifacts, languages=("python",))
    analyze = CodeQLScanner.analyze
    original_read = EvidenceService.read

    def two_alerts(self, database, output, log, plan):
        analyze(self, database, output, log, plan)
        sarif = json.loads(output.read_bytes())
        rows = sarif["runs"][0]["results"]
        unreadable = deepcopy(rows[0])
        unreadable["locations"][0]["physicalLocation"]["artifactLocation"]["uri"] = (
            "unreadable.py"
        )
        rows.append(unreadable)
        output.write_text(json.dumps(sarif), encoding="utf-8")

    def selective_read(self, file, *args, **kwargs):
        if file == "unreadable.py" and self._kernel.spec.operation == "review":
            raise AuditError("Source encoding unavailable", code="source_unreadable")
        return original_read(self, file, *args, **kwargs)

    monkeypatch.setattr(CodeQLScanner, "analyze", two_alerts)
    monkeypatch.setattr(EvidenceService, "read", selective_read)
    value = make_dual(case, settings).model_dump(mode="json")
    value["source"] = snapshot.model_dump(mode="json")
    value["inputs"]["review"]["scheduler"] = "evidence_v3"
    spec = validate_spec(value)
    context = prepare(spec, root=case.ledger.root, settings=settings)
    result = execute(spec, context)
    assert result.execution_status == "completed"
    review = context.executions.inspect(child_id(spec.execution_id, "review"))
    assert review.execution_status == "completed"
    from semflow_research.public.discovery_results import read_result

    published = read_result(review.execution_id, root=case.ledger.root)
    records = {row.location.path: row for row in published.review_report.records}
    assert records["unreadable.py"].execution_state == "not_scheduled"
    assert records["unreadable.py"].stop_code == "source_unavailable"
    assert records["unreadable.py"].assessment is None
    assert records["app.py"].assessment.conclusion == "insufficient"
    assert len(published.candidates) == 3


def test_review_scope_omissions_remain_original_unreviewed_candidates(
    research_case, settings, scanner, model
):
    from semflow_research.runtime.sources import capture

    case = research_case
    (case.source / "other.py").write_text("value = 1\n")
    snapshot = capture(case.source, artifacts=case.artifacts, languages=("python",))
    spec = make_dual(case, settings)
    value = spec.model_dump(mode="json")
    value["source"] = snapshot.model_dump(mode="json")
    value["inputs"]["review"]["scope_paths"] = ["other.py"]
    spec = validate_spec(value)
    context = prepare(spec, root=case.ledger.root, settings=settings)
    result = execute(spec, context)
    assert (
        result.execution_status == "completed"
        and result.completeness.status == "partial"
    )
    received = read_output(context, result)
    _, candidates = resolve_bundle(received, result.result.candidates, CandidateBundle)
    assert len(candidates.records) == 2
    assert {row.execution_id for row in candidates.records} == {
        child_id(spec.execution_id, "scan"),
        child_id(spec.execution_id, "scout"),
    }
    assert {
        ref.entity_id for ref in result.result.coverage.unreviewed_candidate_refs
    } == {row.candidate_id for row in candidates.records}
    assert len(model) == 1  # An empty selected review scope makes no model call.
