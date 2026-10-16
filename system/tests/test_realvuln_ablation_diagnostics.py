"""Keep scoring entities, unresolved candidates and retry counts distinct."""

from scripts.benchmarks.realvuln_ablation_diagnostics import (
    diagnose,
    discovery_projects,
)
from scripts.benchmarks.realvuln_ablation_io import csv_write, read
from scripts.benchmarks.realvuln_prepare import save


def test_multi_cwe_unresolved_and_repeated_rejection_accounting(tmp_path):
    csv_write(
        tmp_path / "review-transitions.csv",
        [
            {
                "group": "D",
                "project_id": "fixture",
                "candidate_id": "one",
                "source": "codeql",
                "review_state": "unknown",
                "before_scored_entities": [
                    {"classification": "TP", "cwe": "CWE-79"},
                    {"classification": "FP", "cwe": "CWE-89"},
                ],
                "rejected_verdicts": [{"reason": "source unread"}] * 2,
                "missing_premises": [],
                "cwe_changed": False,
                "location_changed": False,
            },
            {
                "group": "D",
                "project_id": "fixture",
                "candidate_id": "two",
                "source": "codeql",
                "review_state": "supported",
                "before_scored_entities": [{"classification": "FP", "cwe": "CWE-94"}],
                "rejected_verdicts": [],
                "missing_premises": [],
                "cwe_changed": True,
                "location_changed": False,
            },
        ],
    )
    save(
        tmp_path / "arms/D/system/fixture/review.json",
        {
            "wall_seconds": 1.0,
            "candidates": [
                {"model_assessment": "unknown"},
                {"model_assessment": "supported"},
            ],
            "stage": {
                "model_calls": [],
                "status": "completed",
                "result": {
                    "coverage_status": "partial",
                    "trace": [{"tool": "read_source"}],
                    "batches": [
                        {
                            "status": "partial",
                            "trace": [{"tool": "read_source", "reused": False}],
                        },
                        {
                            "status": "completed",
                            "trace": [{"tool": "read_source", "reused": True}],
                        },
                    ],
                    "stop_reason": None,
                },
            },
        },
    )
    result = diagnose(tmp_path)["D"]
    assert result["candidate_states"] == {"unknown": 1, "supported": 1}
    assert result["before_scored_entity_states"] == {
        "TP": {"unknown": 1},
        "FP": {"unknown": 1, "supported": 1},
    }
    assert result["rejected_attempts_by_reason"] == {"source unread": 2}
    assert result["rejected_unique_candidates_by_reason"] == {"source unread": 1}
    assert result["cwe_changed_candidates"] == 1
    assert result["actual_tools"] == {"read_source": 2}
    assert result["reused_tool_observations"] == {"read_source": 1}
    assert result["partial_last_context_trace_tools"] == {"read_source": 1}
    assert "excluded" not in result["candidate_states"]
    csv_write(
        tmp_path / "discovery-overlap.csv",
        [
            {
                "project_id": "fixture",
                "codeql_independent_hit": a,
                "scout_independent_hit": b,
                "C_union_hit": c,
            }
            for a, b, c in [(True, True, True), (False, False, True)]
        ],
    )
    discovery_projects(tmp_path)
    assert read(tmp_path / "review-diagnostics.json")["D"] == result
    import csv

    row = next(csv.DictReader((tmp_path / "discovery-overlap-per-project.csv").open()))
    assert row["both"] == "1" and row["neither"] == "1"
    assert row["C_union_hit"] == "2"
