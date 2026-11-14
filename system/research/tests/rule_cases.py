"""Explicit model/CodeQL substitutes for rule control and data-boundary tests."""

import json
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from openai.types.chat import ChatCompletion
from semflow_contracts.corpus import CorpusDocument
from semflow_contracts.runs import validate_spec
from semflow_research.adapters.codeql.custom import write_fixtures
from semflow_research.adapters.snapshot import snapshot_digest
from semflow_research.public.corpus import freeze
from semflow_research.public.toolchains import capture

QUERY = """/**
 * @name Explicit eval anchor
 * @description Detect direct evaluation calls for human review.
 * @kind problem
 * @problem.severity warning
 * @precision medium
 * @id audit/test-eval
 */
import python
from Call c
where c.getFunc() instanceof Name and c.getFunc().(Name).getId() = "eval"
select c, "Evaluation anchor."
"""


def install_substitutes(monkeypatch, phases, *, real_tools=False):
    def create(**kwargs):
        payload = json.loads(kwargs["messages"][-1]["content"])[
            "untrusted_analysis_material"
        ]
        phase = payload["phase"]
        phases.append(phase)
        if phase == "inspect_semantics":
            source = next(r for r in payload["evidence"] if r["kind"] == "code")
            body = {
                "action": "ready",
                "project_overview": "The project evaluates input",
                "target_flow": "Input is read and passed to dynamic evaluation",
                "modification_semantics": "Generate a query observing this API call",
                "facts": [
                    {
                        "statement": "The actual source calls eval",
                        "state": "supported",
                        "evidence_ids": [source["id"]],
                        "category": "security",
                        "critical": True,
                    }
                ],
            }
        else:
            assert phase == "generate_rule", phase
            body = {
                "purpose": payload["purpose"],
                "title": "Explicit eval anchor",
                "strategy": "new_query",
                "coverage_analysis": "A direct call anchor requires later human dataflow assessment",
                "query": QUERY,
                "modules": {},
                "knowledge_ids": [payload["knowledge"][0]["id"]],
                "positive": {
                    "files": {"positive.py": "value = eval(input())\n"},
                    "expected": [{"file": "positive.py", "line": 1}],
                },
                "negative": {
                    "files": {"negative.py": "value = int(input())\n"},
                    "expected": [],
                },
            }
        if payload.get("generation_mode") == "grounded_detector_spec":
            body = {
                key: value
                for key, value in body.items()
                if key not in {"query", "modules", "strategy"}
            }
            body.update(
                language=payload["language"],
                operation="eval",
                source_model="baseline",
                sources=[],
            )
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

    monkeypatch.setattr(
        "semflow_research.adapters.ai.provider.OpenAI",
        lambda **kw: SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create)),
            base_url="http://scripted.invalid/v1",
        ),
    )
    if real_tools:
        return  # The opt-in gate substitutes only model output; CodeQL stays real.
    monkeypatch.setattr(
        "semflow_research.adapters.codeql.scanner.CodeQLScanner.version",
        lambda self: "scripted-codeql",
    )

    def compile(pack, log, *, _kernel):
        assert 'getId() = "eval"' in (pack / "generated.ql").read_text()
        log.write_text("Scripted CodeQL compiler, not a real query compilation")

    def validate(directory, pack, language, fixtures, *, _kernel):
        phases.append("fixture_validation")
        tests = {}
        for kind, fixture in fixtures.items():
            write_fixtures(directory / kind, language, fixture)
            tests[kind] = {
                "status": "passed",
                "expected": fixture["expected"],
                "actual": fixture["expected"],
                "findings": [],
                "snapshot_hash": snapshot_digest(directory / kind),
            }
        return {
            "status": "passed",
            "compile": "passed",
            "tests": tests,
            "codeql_version": "scripted-codeql",
            "meaning": "Explicit CodeQL execution substitute for control-boundary tests",
        }

    monkeypatch.setattr("semflow_research.rules.rule_synthesis.compile_query", compile)
    monkeypatch.setattr(
        "semflow_research.rules.rule_synthesis.validate_fixtures", validate
    )
    monkeypatch.setattr("semflow_research.rules.rules.validate_fixtures", validate)
    monkeypatch.setattr(
        "semflow_research.rules.rule_holdouts.validate_fixtures", validate
    )


def rule_spec(case, settings):
    pack = settings.CODEQL_PACK_PATH / "codeql/python-all/test"
    pack.mkdir(parents=True)
    (pack / "qlpack.yml").write_text(
        "name: codeql/python-all\nversion: test\nlibrary: true\n"
    )
    (pack / "codeql-pack.lock.yml").write_text(
        "dependencies:\n  codeql/python-all:\n    version: test\n"
    )
    toolchain = capture(
        root=case.ledger.root,
        owner_execution_id=case.execution_id,
        language="python",
        settings=settings,
    )
    corpus = freeze(
        tuple(
            CorpusDocument(
                document_id=uuid4(),
                collection=collection,
                version="test-v1",
                title=collection,
                source="explicit:" + collection,
                language="python",
                created_at=datetime.now(UTC),
                chunks=("CodeQL eval API reference and examples " + QUERY,),
                provenance={
                    "api_version": "test",
                    "validation": {"status": "passed", "kind": "compile_only"},
                },
            )
            for collection in ("reference", "rule_example")
        ),
        root=case.ledger.root,
        owner_execution_id=case.execution_id,
    )
    prompt = case.artifacts.commit(
        b"Scripted research test prompt", kind="prompt", schema_version="prompt/1"
    )
    value = case.spec.model_dump(mode="json")
    value.update(
        execution_id=str(uuid4()),
        module="rules",
        operation="generate",
        model={
            "provider": "scripted-test",
            "model": "scripted",
            "endpoint_profile": "scripted",
            "output_schema_version": "1",
            "output_tokens": 4000,
        },
        prompts=[
            {
                "role": "rule",
                "template_id": "rule",
                "version": "different-prompt-9",
                "content": prompt.model_dump(mode="json"),
                "sha256": prompt.sha256,
            }
        ],
        inputs={
            "purpose": "review_anchor",
            "requirement": "Observe direct dynamic evaluation calls for subsequent human review",
            "source_paths": ["app.py"],
            "strategy": "new_query",
            "corpus": corpus.model_dump(mode="json"),
            "retrieval": {
                "mode": "bm25",
                "collection_routing": False,
                "top_k": 1,
                "version": "1",
            },
            "generation": {
                "version": "1",
                "full_feedback": True,
                "generation_constraint": False,
                "progress_feedback": True,
                "compact_context": True,
                "source_preparation_context": True,
                "rag_before_inspection": True,
            },
            "development": {
                "compile": True,
                "project_replay": False,
                "query_pack": toolchain.model_dump(mode="json"),
            },
            "acceptance": {"fixture_validation": True},
        },
    )
    value["implementation"]["method_version"] = "8"
    value["policy"].update(
        max_calls=8, max_tokens=300000, max_seconds=120, max_context_chars=40000
    )
    return validate_spec(value)
