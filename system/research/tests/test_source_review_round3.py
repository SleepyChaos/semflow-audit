"""Regression cases for auditable Scout recovery and conservative review planning."""

import json

import pytest
from pydantic import ValidationError
from semflow_contracts.modelio.discovery_semantics import FinalScoutResponseV6
from semflow_research.adapters.ai import scout_response
from semflow_research.discovery import review_scheduling


def recover(body):
    raw = json.dumps(body)
    with pytest.raises(ValidationError) as error:
        FinalScoutResponseV6.model_validate_json(raw)
    return scout_response.recover_scout_format(raw, FinalScoutResponseV6, error.value)


def test_recover_exact_status_conclusion_slot_mixup():
    body = {
        "action": "final",
        "task_checks": [
            {
                "task_id": "input_injection",
                "status": "no_condition_identified",
                "conclusion": "no_condition_identified",
                "reason": "Actual supplied code was examined.",
            }
        ],
    }
    recovered = recover(body)
    assert recovered.response.task_checks[0].status == "investigated"
    assert recovered.response.task_checks[0].conclusion == "no_condition_identified"
    assert recovered.response.task_checks[0].evidence_ids == []
    assert recovered.edits[0]["kind"] == "exact_enum_alias"


def test_unknown_status_and_substantive_candidate_overflow_remain_errors():
    assert (
        recover(
            {
                "action": "final",
                "task_checks": [
                    {
                        "task_id": "input_injection",
                        "status": "almost_safe",
                        "conclusion": "no_condition_identified",
                        "reason": "Actual supplied code was examined.",
                    }
                ],
            }
        )
        is None
    )


def test_known_conclusion_in_wrong_slot_does_not_override_different_conclusion():
    assert (
        recover(
            {
                "action": "final",
                "task_checks": [
                    {
                        "task_id": "input_injection",
                        "status": "suspicious",
                        "conclusion": "unknown",
                        "reason": "Actual supplied code was examined.",
                    }
                ],
            }
        )
        is None
    )


def entry(identifier, rule, line, origin_line=1):
    point = {"file": "worker.py", "line": line, "column": 4, "end_line": line}
    return {
        "candidate_id": identifier,
        "origin": "static",
        "location": point,
        "static_alert": {
            "rule": rule,
            "message": "A static condition remains to be assessed.",
            "security_severity": "9.8",
            "tags": ["security"],
            "locations": [point],
            "code_flows": [[{"file": "entry.py", "line": origin_line}, point]],
        },
    }


def test_cluster_only_identical_source_paths_and_preserve_members():
    rows = [
        entry("a", "r1", 10),
        entry("b", "r1", 10),
        entry("c", "r1", 10, 2),
        entry("d", "r2", 10),
    ]
    clusters = review_scheduling.cluster_alerts(rows)
    assert [tuple(r["candidate_id"] for r in group) for group in clusters] == [
        ("a", "b"),
        ("c",),
        ("d",),
    ]


def test_review_frontier_reserves_different_risk_families():
    rows = [entry("a", "r1", 10), entry("b", "r1", 12), entry("c", "r2", 14)]
    plan = review_scheduling.cluster_frontier(rows)
    assert [r["candidate_id"] for r in plan.ranked] == ["a", "c", "b"]


def test_linked_source_prefers_not_yet_read_documented_points():
    from semflow_research.discovery.review_path_evidence import missing_path_points

    row = entry("a", "r1", 10)
    row["static_alert"]["code_flows"][0].insert(1, {"file": "peer.py", "line": 12})
    existing = [
        {
            "kind": "code",
            "reference": {"file": "entry.py", "start_line": 1, "end_line": 3},
        }
    ]
    result = list(missing_path_points(row, existing))
    assert [(p["file"], p["line"]) for p in result] == [
        ("peer.py", 12),
        ("worker.py", 10),
    ]


def test_mixed_format_recovery_reports_the_display_shortening():
    recovered = recover(
        {
            "action": "final",
            "task_checks": [
                {
                    "task_id": "input_injection",
                    "status": "suspicious",
                    "conclusion": "suspicious",
                    "reason": "A bounded display note. " * 24,
                }
            ],
        }
    )
    assert recovered.response.task_checks[0].status == "investigated"
    assert recovered.classification == "revalidated_mixed_format"


def test_exact_clustering_keeps_distinct_path_metadata():
    first = entry("one", "rule", 10)
    second = entry("two", "rule", 10)
    first["static_alert"]["code_flows"][0][0]["message"] = "First branch"
    second["static_alert"]["code_flows"][0][0]["message"] = "Second branch"
    assert len(review_scheduling.cluster_alerts([first, second])) == 2


def test_candidate_feedback_retains_its_counterevidence_and_path_seeds():
    from semflow_research.discovery.review_navigation_feedback import (
        _retain_candidate_pages,
    )

    source = {
        "targets": [{"candidate_id": "target", "evidence_ids": ["anchor"]}],
        "source_path_seeds": [
            {"candidate_id": "target", "evidence_id": "path"},
            {"candidate_id": "another", "evidence_id": "irrelevant"},
        ],
        "evidence": [
            {"id": name}
            for name in ("anchor", "path", "citation", "counter", "irrelevant")
        ],
    }
    _retain_candidate_pages(
        source,
        {"evidence_ids": ["citation"], "counterevidence_ids": ["counter"]},
        "target",
    )
    assert [row["id"] for row in source["evidence"]] == [
        "anchor",
        "path",
        "citation",
        "counter",
    ]
    assert [row["evidence_id"] for row in source["source_path_seeds"]] == ["path"]
