from semflow_research.discovery.review_handoff import candidate_handoffs


def entry(identifier):
    return {
        "candidate_id": identifier,
        "origin": "static",
        "location": {"file": "app.py", "line": 4},
    }


def test_all_targets_get_handoffs_with_distinct_runner_outcomes():
    targets = ["omitted", "rejected", "failed", "interrupted", "out_of_scope"]
    result = {
        "schedule": {"candidate_ids": targets[:-1]},
        "stop_reason": "rate_limited",
        "batches": [
            {
                "batch_id": "finished",
                "candidate_ids": targets[:2],
                "rejected_assessments": [
                    {"candidate_id": "rejected", "reason": "Unverified citation"},
                ],
            },
            {"batch_id": "failed", "candidate_ids": ["failed"], "code": "timeout"},
        ],
    }

    records = candidate_handoffs([entry(value) for value in targets], result)

    assert [row["candidate_id"] for row in records] == targets
    assert [row["reason_code"] for row in records] == [
        "assessment_omitted",
        "assessment_rejected",
        "timeout",
        "rate_limited",
        "outside_batch_limit",
    ]
    assert all(
        row["state"] == "unreviewed" and row["conclusion"] is None for row in records
    )


def test_handoff_keeps_candidate_evidence_and_feedback_separate():
    result = {
        "batches": [
            {
                "batch_id": "batch",
                "candidate_ids": ["one", "two"],
                "assessments": [
                    {
                        "candidate_id": "one",
                        "assessment": "insufficient",
                        "evidence_ids": ["one-page"],
                        "checked_premises": ["Verified import"],
                        "missing_premises": ["Check definition"],
                        "runtime_unknowns": ["Deployment settings"],
                    },
                    {
                        "candidate_id": "two",
                        "assessment": "supported",
                        "evidence_ids": ["two-page"],
                    },
                ],
            },
        ],
        "review_feedback_attempts": [
            {"id": "attempt", "candidate_ids": ["one"], "status": "no_source_progress"},
        ],
    }

    one, two = candidate_handoffs([entry("one"), entry("two")], result)

    assert one["state"] == "unresolved"
    assert one["evidence_ids"] == ["one-page"]
    assert one["missing_premises"] == ["Check definition"]
    assert one["runtime_unknowns"] == ["Deployment settings"]
    assert one["feedback_attempts"] == [
        {"id": "attempt", "status": "no_source_progress"}
    ]
    assert two["state"] == "assessed"
    assert two["evidence_ids"] == ["two-page"]
    assert two["feedback_attempts"] == []


def test_next_action_uses_remaining_source_ranges_before_asking_for_policy(tmp_path):
    from types import SimpleNamespace

    from semflow_contracts.review_handoff import ReviewSourceWindow
    from semflow_research.discovery.review_next_action import merge_windows, next_action

    path = tmp_path / "policy.md"
    path.write_text("first\nsecond\nthird\n", encoding="utf-8")
    evidence = SimpleNamespace(allowed=lambda _: path)
    assessment = {
        "security_property": "authentication",
        "missing_premises": ["Check policy.md for a project requirement"],
        "premises": [
            {
                "premise": "input_or_policy",
                "status": "missing",
                "policy_basis": "unknown",
                "reason": "The project requirement is unknown.",
            }
        ],
    }
    seen = merge_windows(
        [ReviewSourceWindow(file="policy.md", start_line=1, end_line=2)]
    )
    action = next_action("unresolved", assessment, seen, evidence)
    assert action.kind == "gather_source"
    assert action.source_windows[0].start_line == action.source_windows[0].end_line == 3
    exhausted = merge_windows([*seen, *action.source_windows])
    assert (
        next_action("unresolved", assessment, exhausted, evidence).kind
        == "collect_material"
    )
    assert next_action("unreviewed", {}, (), evidence).kind == "retry_execution"
