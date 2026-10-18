import copy
from types import SimpleNamespace

import pytest
from app.services.candidate_groups import project_candidates


def candidate(identifier, origin="ai", *, identity=None, line=9, weakness="CWE-95"):
    return {
        "id": identifier,
        "audit_id": "audit-one",
        "origin": origin,
        "identity_key": identity or f"{origin}:{identifier}",
        "location": {"file": "app.py", "line": line},
        "weakness": weakness,
        "status": "confirmed",
        "created_at": "2026-10-18T06:00:00Z",
        "evidence_ids": [f"evidence-{identifier}"],
        "classification": {"source": "ai", "status": "confirmed"},
        "review": {
            "evaluated": True,
            "snapshot_hash": "snapshot-one",
            "status": "supported",
            "detail": {
                "exploitation": {"source_quote": "return str(eval(expression))"}
            },
        },
    }


def relation(kind="same_root_cause", snapshot="snapshot-one"):
    return SimpleNamespace(
        kind="review",
        status="completed",
        audit_id="audit-one",
        result={
            "snapshot_hash": snapshot,
            "root_relations": [
                {
                    "candidate_ids": ["static", "ai"],
                    "relationship": kind,
                    "evidence_ids": ["evidence-static"],
                }
            ],
        },
    )


def test_same_sink_merges_sources_and_retry_ids_without_mutating_history():
    static, ai = candidate("static", "static"), candidate("ai")
    scout = candidate("scout", identity=ai["identity_key"])
    scout.update(status="pending", review=None, classification={"source": "pending"})
    rows = [scout, static, ai]
    original = copy.deepcopy(rows)
    groups = project_candidates(rows, [relation()], "snapshot-one")
    assert len(groups) == 1
    assert set(groups[0]["issue"]["member_ids"]) == {"static", "ai", "scout"}
    assert set(groups[0]["issue"]["current_ids"]) == {"static", "ai"}
    assert groups[0]["issue"]["origins"] == ["ai", "static"]
    assert set(groups[0]["evidence_ids"]) == {"evidence-ai", "evidence-static"}
    assert rows == original


@pytest.mark.parametrize(
    "change",
    [
        {"weakness": "CWE-79"},
        {"weakness": "unknown"},
        {"location": {"file": "app.py", "line": 10}},
        {"location": {"file": "other.py", "line": 9}},
        {"audit_id": "another-audit"},
    ],
)
def test_distinct_security_properties_locations_and_tasks_are_not_merged(change):
    ai = candidate("ai")
    ai.update(change)
    assert (
        len(
            project_candidates(
                [candidate("static", "static"), ai], [relation()], "snapshot-one"
            )
        )
        == 2
    )


@pytest.mark.parametrize("kind", ["distinct", "related"])
def test_explicit_distinct_or_related_assessments_prevent_automatic_merging(kind):
    assert (
        len(
            project_candidates(
                [candidate("static", "static"), candidate("ai")],
                [relation(kind)],
                "snapshot-one",
            )
        )
        == 2
    )


def test_same_line_different_calls_or_stale_evidence_do_not_merge():
    a, b = candidate("static", "static"), candidate("ai")
    a["location"]["column"], b["location"]["column"] = 10, 40
    assert len(project_candidates([a, b], [relation()], "snapshot-one")) == 2
    a["location"].pop("column")
    b["location"].pop("column")
    b["review"]["snapshot_hash"] = "stale-snapshot"
    assert len(project_candidates([a, b], [relation()], "snapshot-one")) == 2


def test_conflicting_verdicts_stay_uncertain_until_human_classification():
    a, b = candidate("static", "static"), candidate("ai")
    b["status"] = b["classification"]["status"] = "excluded"
    group = project_candidates([a, b], [], "snapshot-one")[0]
    assert group["status"] == "insufficient" and group["issue"]["conflict"]
    b["classification"]["source"] = "human"
    group = project_candidates([a, b], [], "snapshot-one")[0]
    assert group["status"] == "excluded" and not group["issue"]["conflict"]


def test_parent_and_eval_cwe_labels_share_only_the_proven_same_operation():
    a, b = candidate("static", "static", weakness="CWE-094"), candidate("ai")
    assert len(project_candidates([a, b], [], "snapshot-one")) == 1
    b["review"]["detail"]["exploitation"]["source_quote"] = "another_eval(other_input)"
    assert len(project_candidates([a, b], [relation()], "snapshot-one")) == 2


def test_shifted_primary_lines_merge_only_with_unambiguous_cited_source():
    a, b = candidate("static", "static"), candidate("ai", line=7)
    material = [
        {
            "id": "evidence-static",
            "audit_id": "audit-one",
            "kind": "code",
            "snapshot_hash": "snapshot-one",
            "reference": {"file": "app.py", "start_line": 1},
            "content": "\n" * 8 + "return str(eval(expression))\n",
        }
    ]
    b["evidence_ids"] = ["evidence-static"]
    assert len(project_candidates([a, b], [], "snapshot-one", material)) == 2
    assert len(project_candidates([a, b], [relation()], "snapshot-one", material)) == 1
    # A repeated statement cannot identify a unique sink from nearby line numbers.
    material[0]["content"] += "\nreturn str(eval(expression))\n"
    a["location"]["line"], b["location"]["line"] = 20, 21
    assert len(project_candidates([a, b], [], "snapshot-one", material)) == 2
