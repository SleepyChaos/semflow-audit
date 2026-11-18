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
