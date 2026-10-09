"""Evidence and context regressions; scripted responses are not model efficacy."""

import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from app.adapters.codeql.grounded_spec import ExternalSource, verify_source
from app.adapters.retrieval.quality import active_records
from app.domain.audit import AuditError
from app.services.rule_context import compact_rule_context

from tests.test_semantic_development import InspectModel, inspector, ready


def test_duplicate_read_returns_existing_evidence_and_resumes(pipeline_context):
    def reply(payload):
        if not payload["tool_trace"]:
            return {
                "action": "tool",
                "tool": {
                    "name": "read_source",
                    "arguments": {"file": "app.py", "start_line": 1, "end_line": 1},
                    "reason": "Understand the external value",
                },
            }
        assert payload["feedback"]["latest_observation"]["reused"]
        assert (
            payload["feedback"]["latest_observation"]["observation"]["id"]
            == payload["evidence"][0]["id"]
        )
        assert "content" not in payload["feedback"]["latest_observation"]["observation"]
        assert payload["evidence"][0]["content"] == "value = eval(input())"
        return ready(payload)

    provider = InspectModel(reply)
    service, source = inspector(pipeline_context, provider)
    service.progressive = True
    first = service.inspect([{"description": "eval risk"}], [source])
    assert first["view"]["facts"][0]["evidence_ids"] == [source["id"]]
    assert service.inspect([{"description": "eval risk"}], [source]) == first
    assert provider.usage["calls"] == 2
    assert not (service.directory / "semantics/tools.json").exists()


def test_repeated_read_loop_is_bounded(pipeline_context):
    provider = InspectModel(
        lambda _: {
            "action": "tool",
            "tool": {
                "name": "read_source",
                "arguments": {"file": "app.py", "start_line": 1, "end_line": 1},
                "reason": "Read the same source again",
            },
        }
    )
    service, source = inspector(pipeline_context, provider)
    service.progressive = True
    with pytest.raises(AuditError, match="重复停滞"):
        service.inspect([{"description": "risk"}], [source])
    assert provider.usage["calls"] == 3


def test_compact_context_keeps_whole_queries_code_and_unknowns():
    rows = [
        {
            "id": str(uuid4()),
            "content": "class Source {}\n" * 800,
            "provenance": {
                "api_version": "4.0.10",
                "official_development_tests": [{"log": "huge" * 10000}],
                "validation": {"kind": "official_development_test", "status": "passed"},
            },
            "corpus": "reference",
        }
    ]
    inspection = {
        "evidence": [{"id": "code-1", "content": "eval(value)"}],
        "view": {
            "unknowns": ["external trust requires confirmation"],
            "facts": [{"evidence_ids": ["code-1"]}],
        },
    }
    original = {
        "knowledge": rows,
        "semantic_inspection": inspection,
        "requirement": "detect eval",
        "compiler_feedback": {"message": "actual error"},
        "previous_candidate": {"query": "the whole previous query"},
    }
    compact = compact_rule_context(original)
    assert compact["knowledge"][0]["content"] == rows[0]["content"]
    assert compact["semantic_inspection"] == inspection
    assert compact["previous_candidate"] == original["previous_candidate"]
    assert compact["compiler_feedback"] == original["compiler_feedback"]
    assert len(json.dumps(original)) - len(json.dumps(compact)) > 35000
    assert "official_development_tests" in original["knowledge"][0]["provenance"]


def source_context(code, trust):
    source_id, trust_id = uuid4(), uuid4()
    source = ExternalSource(
        module="events_api",
        member="fetch_event",
        source_evidence_id=source_id,
        trust_evidence_id=trust_id,
    )
    context = {
        "knowledge": [{"content": "moduleImport getMember getACall class Source"}],
        "semantic_inspection": {
            "evidence": [
                {
                    "id": str(source_id),
                    "kind": "code",
                    "reference": {"file": "handler.py", "start_line": 1},
                    "content": code,
                },
                {"id": str(trust_id), "content": trust},
            ]
        },
    }
    return source, context


@pytest.mark.parametrize(
    "code",
    [
        "import events_api as external\nv = external.fetch_event()",
        "from events_api import fetch_event as fetch\nv = fetch()",
    ],
)
def test_source_model_verifies_actual_alias_bindings(code):
    source, context = source_context(
        code, "events_api.fetch_event returns untrusted external text"
    )
    verify_source(source, context)


@pytest.mark.parametrize(
    "code,trust",
    [
        (
            "import other_api as events_api\nv = events_api.fetch_event()",
            "events_api.fetch_event returns untrusted external text",
        ),
        (
            "import events_api\nv = events_api.fetch_event()",
            "events_api.fetch_event returns trusted external configuration",
        ),
    ],
)
def test_source_model_rejects_fabricated_api_or_unproved_trust(code, trust):
    source, context = source_context(code, trust)
    with pytest.raises(AuditError):
        verify_source(source, context)


def test_active_multi_cwe_filter_excludes_failed_latest_and_unverified():
    def row(source, version, status, ids):
        return SimpleNamespace(
            owner_id=None,
            source=source,
            version=version,
            corpus="rule_example",
            provenance={
                "validation": {"status": status, "kind": "official_development_test"},
                "cwe": "CWE-089",
                "cwe_ids": ids,
            },
        )

    current = row("SqlInjection", "new", "passed", ["CWE-089", "CWE-943"])
    failed = row("Bad", "new", "failed", ["CWE-943"])
    stale = row("Bad", "old", "passed", ["CWE-943"])
    unknown = row("Unverified", "new", "not_run", ["CWE-943"])
    assert active_records([current, failed, stale, unknown], "CWE-943") == [current]
