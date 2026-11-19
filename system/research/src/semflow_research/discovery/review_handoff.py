"""Candidate diagnostics for the versioned discovery trace.

Peer: platform discovery projection and frontend ReviewHandoff.
These records describe execution and evidence; assessments remain authoritative.
"""

from collections import defaultdict

from semflow_contracts.review_handoff import ReviewNextAction, ReviewSourceWindow

from semflow_research.discovery.review_next_action import (
    merge_windows,
    next_action,
    source_windows_seen,
)


def candidate_handoffs(entries, result, *, directory=None, evidence=None):
    """Keep one record per frozen target, including targets with no model output."""
    batches = defaultdict(list)
    attempts = defaultdict(list)
    for batch in result.get("batches", []):
        for candidate_id in batch["candidate_ids"]:
            batches[candidate_id].append(batch)
    for attempt in result.get("review_feedback_attempts", []):
        for candidate_id in attempt["candidate_ids"]:
            attempts[candidate_id].append(attempt)

    scheduled = result.get("schedule", {}).get("candidate_ids")
    scheduled = None if scheduled is None else set(scheduled)
    return [
        _handoff(
            entry,
            batches[entry["candidate_id"]],
            attempts[entry["candidate_id"]],
            scheduled,
            result.get("stop_reason"),
            directory=directory,
            evidence=evidence,
            previous=result.get("review_continuation", {}),
        )
        for entry in entries
    ]


def _handoff(
    entry, batches, attempts, scheduled, stop_reason, *, directory, evidence, previous
):
    candidate_id = entry["candidate_id"]
    assessments = [
        row
        for batch in batches
        for row in batch.get("assessments", [])
        if row["candidate_id"] == candidate_id
    ]
    assessment = assessments[-1] if assessments else {}
    rejected = [
        row["reason"]
        for batch in batches
        for row in batch.get("rejected_assessments", [])
        if row["candidate_id"] == candidate_id
    ]
    conclusion = assessment.get("assessment")
    missing = [
        {
            "role": premise["premise"],
            "reason": premise["reason"],
            "evidence_ids": premise.get("evidence_ids", []),
        }
        for premise in assessment.get("premises", [])
        if premise["status"] == "missing"
    ]
    state, cause = _disposition(
        conclusion, rejected, batches, scheduled, candidate_id, stop_reason
    )
    guidance = {}
    if directory is not None and evidence is not None:
        seen = [
            window
            for batch in batches
            for window in source_windows_seen(directory, batch, candidate_id)
        ]
        seen.extend(
            ReviewSourceWindow.model_validate(window)
            for window in previous.get("previous_source_windows", [])
        )
        seen = merge_windows(seen)
        plan = None
        if getattr(evidence, "repository_navigation", False) is True:
            from semflow_research.discovery.review_gap_planner import plan_gaps
            from semflow_research.discovery.review_navigation_feedback import (
                gap_history,
            )

            previous_gaps = gap_history(attempts)
            acquired = tuple(
                ReviewSourceWindow(
                    **{k: event[k] for k in ("file", "start_line", "end_line")}
                )
                for attempt in attempts
                for event in attempt.get("source_events", ())
                if event.get("origin") == "repository_locator"
                and event.get("status") == "supplied"
            )
            plan = plan_gaps(
                assessment, evidence, merge_windows([*seen, *acquired]), previous_gaps
            )
            rows = {gap.gap_id: gap for gap in [*previous_gaps, *plan.gaps]}
            guidance["evidence_gaps"] = [
                gap.model_dump(mode="json") for gap in rows.values()
            ]
        action = next_action(state, assessment, seen, evidence, plan)
        if (
            plan is not None
            and state == "unresolved"
            and action.kind != "gather_source"
            and attempts
            and attempts[-1]["status"] == "incomplete"
            and attempts[-1].get("code")
            in {
                "provider_error",
                "timeout",
                "rate_limited",
                "budget_exhausted",
                "unit_budget",
            }
            and any(
                event.get("status") == "supplied"
                for event in attempts[-1].get("source_events", ())
            )
        ):
            action = ReviewNextAction(kind="retry_execution")
        guidance.update(
            {
                "next_action": action.model_dump(mode="json"),
                "observed_source_windows": [
                    window.model_dump(mode="json") for window in seen
                ],
            }
        )
    return {
        **guidance,
        "candidate_id": candidate_id,
        "origin": entry["origin"],
        "location": entry["location"],
        "state": state,
        "reason_code": cause,
        "conclusion": conclusion,
        "reason": assessment.get("reason"),
        "security_property": assessment.get("security_property"),
        "checked_premises": assessment.get("checked_premises", []),
        "missing_premises": assessment.get("missing_premises", []),
        "missing_checks": missing,
        "runtime_unknowns": assessment.get("runtime_unknowns", []),
        "evidence_ids": assessment.get("evidence_ids", []),
        "counterevidence_ids": assessment.get("counterevidence_ids", []),
        "rejected_reasons": rejected,
        "batch_ids": [batch["batch_id"] for batch in batches],
        "feedback_attempts": [
            {key: attempt[key] for key in ("id", "status", "code") if key in attempt}
            for attempt in attempts
        ],
    }


def _disposition(conclusion, rejected, batches, scheduled, candidate_id, stop_reason):
    if conclusion in {"supported", "excluded"}:
        return "assessed", None
    if conclusion in {"insufficient", "pending"}:
        return (
            "unresolved",
            "insufficient_evidence"
            if conclusion == "insufficient"
            else "pending_assessment",
        )
    if rejected:
        return "unreviewed", "assessment_rejected"
    if batches:
        last_batch = batches[-1]
        return "unreviewed", last_batch.get("code") or "assessment_omitted"
    if scheduled is not None and candidate_id not in scheduled:
        return "unreviewed", "outside_batch_limit"
    return "unreviewed", stop_reason or "not_attempted"
