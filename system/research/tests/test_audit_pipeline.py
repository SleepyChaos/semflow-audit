"""Regressions for failure isolation and fixed-budget review planning."""

import json
from uuid import uuid4

import pytest
from pydantic import ValidationError
from semflow_contracts.modelio.discovery_semantics import FinalScoutResponseV6
from semflow_research.adapters.ai import scout_response
from semflow_research.discovery import review_scheduling


def scout_final(findings):
    return {
        "action": "final",
        "task_checks": [
            {
                "task_id": "input_injection",
                "status": "unknown",
                "reason": "No final source conclusion is available.",
            }
        ],
        "findings": findings,
    }


def source_finding():
    return {
        "title": "Source behavior requires assessment",
        "weakness": "unknown",
        "primary_location": {"file": "src/app.py", "line": 5},
        "security_property": "other",
        "security_condition": "Validate the source assertion against the implementation.",
        "observation": "The operation requires independent evidence before classification.",
        "operation_quote": "return data",
        "evidence_ids": [str(uuid4())],
    }


def recover(body):
    raw = json.dumps(body)
    with pytest.raises(ValidationError) as exc:
        FinalScoutResponseV6.model_validate_json(raw)
    return scout_response.recover_scout_format(
        raw, FinalScoutResponseV6, exc.value, isolate_findings=True
    )


def test_partial_scout_preserves_verbatim_good_candidate_and_rejects_bad():
    kept = source_finding()
    skipped = {**source_finding(), "observation": "short"}
    result = recover(scout_final([kept, skipped]))
    assert [r.title for r in result.response.findings] == [kept["title"]]
    assert result.response.findings[0].observation == kept["observation"]
    assert [edit["path"] for edit in result.edits] == [["findings", 1]]
    assert result.classification == "revalidated_partial_findings"


def test_partial_scout_cannot_discard_all_candidates_or_an_invalid_envelope():
    invalid = {**source_finding(), "security_property": "unknown"}
    assert recover(scout_final([invalid])) is None
    assert (
        recover({**scout_final([source_finding(), invalid]), "task_checks": []}) is None
    )
    assert (
        recover({**scout_final([source_finding(), invalid]), "action": "tool"}) is None
    )


def static_entry(identifier, module, family, *, available=True):
    point = {"file": f"{module}/unit.py", "line": 5}
    return {
        "candidate_id": identifier,
        "origin": "static",
        "location": point,
        "static_alert": {
            "rule": family,
            "locations": [point],
            "code_flows": [],
            "security_severity": 9.8,
        },
        "hypothesis": "Source evidence is necessary.",
        **({} if available else {"source_unavailable": "source_unreadable"}),
    }


def test_review_frontier_rotates_across_origins_modules_and_risk_families():
    rows = [
        static_entry("alpha", "a", "risk-a"),
        static_entry("beta", "a", "risk-a"),
        static_entry("gamma", "b", "risk-a"),
        static_entry("delta", "c", "risk-b"),
        static_entry("bad", "0", "risk-c", available=False),
        {
            "candidate_id": "scout",
            "origin": "scout",
            "location": {"file": "z/unit.py", "line": 4},
            "weakness": "unknown",
            "hypothesis": {},
        },
    ]
    frontier = review_scheduling.evidence_frontier(rows)
    assert len(frontier.ranked) == 5
    selected = [row["candidate_id"] for row in frontier.ranked[:3]]
    assert "scout" in selected
    assert "delta" in selected
    assert "bad" not in {row["candidate_id"] for row in frontier.ranked}
    assert frontier.previous_ranks["bad"] > 0


def test_scout_budget_leaves_review_capacity_without_increasing_parent_budget():
    from semflow_research.runtime.calls import _scout_limits

    assert _scout_limits(
        {"max_calls": 32, "max_tokens": 320000, "max_seconds": 900}
    ) == {
        "max_calls": 24,
        "max_tokens": 240000,
        "max_seconds": 675,
    }
    assert _scout_limits({"max_calls": 1, "max_tokens": None, "max_seconds": None}) == {
        "max_calls": 0,
        "max_tokens": None,
        "max_seconds": None,
    }


def test_unavailable_and_duplicate_have_distinct_handoffs():
    from semflow_research.discovery.review_handoff import candidate_handoffs
    from semflow_research.runtime.review_report import _execution_state

    rows = [
        static_entry("bad", "src", "risk-a", available=False),
        static_entry("duplicate", "src", "risk-a"),
        static_entry("remaining", "src", "risk-a"),
    ]
    result = {
        "schedule": {
            "scheduler": "evidence_v3",
            "candidate_ids": [],
            "decisions": [
                {"candidate_id": "bad", "disposition": "source_unavailable"},
                {"candidate_id": "duplicate", "disposition": "exact_static_duplicate"},
            ],
        },
    }
    handoffs = candidate_handoffs(rows, result)
    assert [h["reason_code"] for h in handoffs] == [
        "source_unavailable",
        "exact_static_duplicate",
        "outside_batch_limit",
    ]
    assert all(_execution_state(row, None, []) == "not_scheduled" for row in handoffs)


def test_scout_window_prefix_values_new_regions_over_repeating_one_function():
    from semflow_research.adapters.scout_scheduling import coverage_order

    files = [
        {"file": "a/f.py", "functions": [{"start_line": 1, "end_line": 80}]},
        {"file": "b/f.py", "functions": [{"start_line": 1, "end_line": 10}]},
    ]
    windows = [
        {
            "id": identity,
            "file": file,
            "module": file.split("/")[0],
            "start_line": start,
            "end_line": end,
            "source_characters": chars,
            "risk": {"score": 8, "reasons": ["same"]},
        }
        for identity, file, start, end, chars in [
            ("first", "a/f.py", 1, 40, 100),
            ("repeat", "a/f.py", 41, 80, 200),
            ("new", "b/f.py", 1, 10, 300),
        ]
    ]
    assert [r["id"] for r in coverage_order(windows, files, 2)] == [
        "first",
        "new",
        "repeat",
    ]


def test_long_detector_message_stays_in_pool_without_overwhelming_source_context():
    from semflow_research.discovery.review_pool import compact_static_target

    entry = static_entry("id", "src", "risk")
    diagnostic = "Deterministic detector metadata. " * 900
    entry["static_alert"]["message"] = diagnostic
    entry["hypothesis"] = diagnostic
    packed = compact_static_target(entry)
    assert len(json.dumps(packed)) < 2500
    assert packed["static_alert"]["rule"] == "risk"
    assert packed["static_alert"]["message_characters"] == len(diagnostic)
    assert entry["static_alert"]["message"] == entry["hypothesis"] == diagnostic
    assert packed["location"] == entry["location"]


def test_repository_navigation_and_scout_agree_on_decorator_range():
    from semflow_research.adapters.project_map import symbols
    from semflow_research.adapters.repository_locator import _python_definitions

    code = "class Service:\n    @bound\n    def handle(self):\n        return 1\n"
    function = symbols(code, "python", risk_aware=True)["functions"][0]
    assert function["qualified_name"] == "Service.handle"
    assert (function["start_line"], function["end_line"]) == (2, 4)
    assert list(_python_definitions("handle", code)) == [(2, 4, "syntax_definition")]
