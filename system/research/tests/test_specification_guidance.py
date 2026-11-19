import json
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from openai.types.chat import ChatCompletion
from semflow_contracts.corpus import CorpusDocument
from semflow_contracts.runs import validate_spec
from semflow_research.discovery.specification_guidance import Guidance
from semflow_research.public.corpus import freeze
from semflow_research.public.discovery import execute
from semflow_research.public.discovery_results import read_result
from semflow_research.public.runtime import prepare


def test_guidance_returns_only_general_norms_and_preserves_source_citation_namespace():
    doc = str(uuid4())
    raw = {
        "document_id": doc,
        "version": "revision",
        "title": "HTML response safety",
        "source": "https://example.org/dataset",
        "content": "Encode untrusted request content for the destination HTML context.",
        "score": 0.016,
        "provenance": {
            "domain": "output",
            "historical_sources": ["CVE-2000-1234"],
            "repository": "upstream/example",
            "source_scope": "vulinstruct_train",
        },
    }
    project = SimpleNamespace(
        context=SimpleNamespace(settings=SimpleNamespace()),
        policy=SimpleNamespace(
            top_k=2, min_shared_terms=2, retrieval_mode="bm25", timeout_seconds=5
        ),
        retriever=SimpleNamespace(retrieve=lambda *args, **kwargs: [raw]),
        document_ids=(doc,),
        corpus_id=uuid4(),
    )
    guidance = Guidance(project)
    receipt, hints = guidance.retrieve(
        "python", "def response(request):\n    return html_context(request.content)"
    )
    assert receipt["status"] == "matched"
    assert receipt["references"][0]["historical_sources"] == ["CVE-2000-1234"]
    assert hints[0]["specification_id"] == doc
    assert "CVE-2000" not in str(hints) and "upstream/example" not in str(hints)
    assert receipt["query_digest"]
    unrelated, no_hints = guidance.retrieve(
        "python", "def circle(radius): return radius * radius"
    )
    assert unrelated["status"] == "no_match"
    assert no_hints == []


def test_optional_retrieval_error_and_timeout_leave_scout_context_usable():
    def fail(*args, **kwargs):
        raise TimeoutError

    project = SimpleNamespace(
        context=SimpleNamespace(settings=SimpleNamespace()),
        policy=SimpleNamespace(
            top_k=2, min_shared_terms=2, retrieval_mode="bm25", timeout_seconds=5
        ),
        retriever=SimpleNamespace(retrieve=fail),
        document_ids=(str(uuid4()),),
        corpus_id=uuid4(),
    )
    receipt, hints = Guidance(project).retrieve(
        "python", "return response(request.content)"
    )
    assert receipt["status"] == "timeout" and not hints


@pytest.mark.parametrize(
    "mode", ("disabled", "matched", "excluded_repository", "future")
)
def test_frozen_specifications_scout_roundtrip(
    research_case, settings, monkeypatch, mode
):
    case = research_case
    root = case.ledger.root
    value = case.spec.model_dump(mode="json")
    prompt = case.artifacts.commit(
        b"Evaluate scoped evidence and preserve unknowns.",
        kind="prompt",
        schema_version="prompt/1",
        media_type="text/plain",
    )
    normative = CorpusDocument(
        document_id=uuid4(),
        collection="reference",
        version="fixture/1",
        title="Input processing",
        source="https://example.invalid/knowledge",
        language="any",
        created_at=datetime(2026, 2, 1, tzinfo=UTC),
        chunks=(
            "Validate input before using eval to enforce the expected execution context.",
        ),
        provenance={
            "source_scope": "vulinstruct_train",
            "repository": "training/example",
            "domain": "input",
            "historical_sources": ["CVE-2000-1234"],
            "vulnerability_analysis": "Do not include a historical answer in the model input.",
        },
    )
    kb = freeze((normative,), root=root, owner_execution_id=uuid4())
    value.update(
        execution_id=str(uuid4()),
        operation="scout",
        inputs={
            "window_policy": {
                "version": "1",
                "max_windows": 1,
                "max_steps_per_window": 1,
                "max_calls": 1,
            },
        },
        model={
            "provider": "scripted-test",
            "model": "scripted",
            "endpoint_profile": "local",
            "output_schema_version": "1",
            "output_tokens": 2300,
        },
        prompts=[
            {
                "role": "scout",
                "template_id": "scout",
                "version": "8",
                "content": prompt.model_dump(mode="json"),
                "sha256": prompt.sha256,
            }
        ],
    )
    if mode != "disabled":
        value["inputs"]["security_specifications"] = {
            "corpus": kb.model_dump(mode="json"),
            "as_of": "2026-01-01" if mode == "future" else "2026-03-01",
            "excluded_repositories": ["https://github.com/training/example.git"]
            if mode == "excluded_repository"
            else [],
        }
    value["implementation"]["method_version"] = "8"
    value["policy"].update(max_tokens=50000, max_context_chars=40000)
    spec = validate_spec(value)
    context = prepare(spec, root=root, settings=settings)
    calls = []

    def reply(**kwargs):
        payload = json.loads(kwargs["messages"][-1]["content"])[
            "untrusted_analysis_material"
        ]
        calls.append(payload)
        body = {
            "action": "final",
            "scope_summary": "Inspected the same scoped application code.",
            "task_checks": [
                {
                    "task_id": t["id"],
                    "status": "unknown",
                    "reason": "The supplied code leaves scope unresolved.",
                }
                for t in payload["inspection_tasks"]
            ],
            "findings": [
                {
                    "title": "Dynamic evaluation of process input",
                    "weakness": "CWE-95",
                    "primary_location": {"file": "app.py", "line": 1},
                    "security_condition": "The caller must control the evaluated value.",
                    "observation": "The target window evaluates a call result.",
                    "missing_premises": ["Caller trust boundary remains unknown."],
                    "operation_quote": "eval(input())",
                    "security_property": "input_injection",
                    "evidence_ids": [payload["evidence"][0]["id"]],
                }
            ],
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
            usage={"prompt_tokens": 100, "completion_tokens": 30, "total_tokens": 130},
        )

    monkeypatch.setattr(context.model.client.chat.completions, "create", reply)
    result = execute(spec, context)
    assert result.execution_status == "completed", result.failure
    view = read_result(spec.execution_id, root=root)
    assert result.usage.calls == 1
    assert len(view.candidates) == len(calls) == 1
    (candidate,) = view.candidates
    (provider_input,) = calls
    assert candidate.origin == "scout"
    assert ("security_specifications" in provider_input) == (mode == "matched")
    assert "CVE-2000-1234" not in str(provider_input)
    (unit,) = view.trace.state["units"]
    if mode == "matched":
        (raw,) = unit["hypotheses"]
        assert raw["discovery_mode"] == "specification_guided"
        assert raw["security_specifications"][0]["specification_id"] == str(
            normative.document_id
        )
        assert unit["specification_lookup"]["status"] == "matched"
    elif mode != "disabled":
        assert unit["specification_lookup"]["status"] == "no_match"
    else:
        assert "specification_lookup" not in unit


def test_review_requires_semantic_counterevidence_when_enabled(tmp_path):
    from semflow_research.discovery.review_obligations import verify_obligations

    source = "def show(value):\n    return formatter(value)\n"
    path = tmp_path / "main.py"
    path.write_text(source, encoding="utf-8")
    assessment = SimpleNamespace(
        assessment="excluded",
        security_property="output_encoding",
        weakness="CWE-79",
        premises=[
            SimpleNamespace(
                premise="operation",
                quote="formatter(value)",
                reason="The observed function is treated as a defense.",
                evidence_ids=[uuid4()],
            )
        ],
        evidence_gaps=[],
        missing_premises=[],
        runtime_unknowns=[],
        detail=SimpleNamespace(exploitation=SimpleNamespace()),
    )
    service = SimpleNamespace(evidence=SimpleNamespace(allowed=lambda _: path))
    facts = verify_obligations(
        service,
        assessment,
        {"location": {"file": "main.py", "line": 2}, "weakness": "CWE-79"},
        [],
        require_refutation=True,
    )
    assert assessment.assessment == "insufficient"
    assert not any(fact["status"] == "refuted" for fact in facts)
