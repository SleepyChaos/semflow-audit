"""Use new evidence and the original batch budget to drive review revisions."""

from semflow_contracts.review_gaps import ReviewEvidenceGap
from semflow_contracts.review_handoff import ReviewSourceWindow

from semflow_research.discovery.discovery_context import (
    refresh_citation_contract,
    refresh_control_context,
)
from semflow_research.discovery.review_feedback import (
    _begin_attempt,
    _pack,
    _target_context,
    update_attempt,
)
from semflow_research.discovery.review_gap_planner import plan_gaps
from semflow_research.domain.errors import AuditError
from semflow_research.evidence.read_tools import window_observations


def gap_history(attempts) -> tuple[ReviewEvidenceGap, ...]:
    latest = {}
    for attempt in attempts:
        for row in attempt.get("evidence_gaps", ()):
            gap = ReviewEvidenceGap.model_validate(row)
            latest[gap.gap_id] = gap
    return tuple(latest.values())


def next_navigation(service, batch_id, result, base, context, remaining, policy):
    if not remaining:
        return None
    attempts = service.repository.get(service.execution_id).result.get(
        "review_feedback_attempts", ()
    )
    targets = {row["candidate_id"] for row in base["targets"]}
    for assessment in result.get("assessments", ()):
        candidate = assessment["candidate_id"]
        if assessment["assessment"] != "insufficient" or candidate not in targets:
            continue
        previous = [item for item in attempts if candidate in item["candidate_ids"]]
        if len(previous) >= policy["max_rounds_per_candidate"]:
            continue
        # Keep source accumulated for this candidate. Other candidates restart
        # from the frozen batch input and their independent evidence budgets.
        active = (
            context
            if [t["candidate_id"] for t in context["targets"]] == [candidate]
            else base
        )
        source = _target_context(active, assessment, batch_id, policy)
        from semflow_research.discovery.review_pool import evidence_intake

        if (
            evidence_intake(service._kernel.spec.inputs.policy) == "linked"
            and active is base
        ):
            # Keep target and cited material. Drop other members' unrelated pages
            # before giving newly acquired evidence its share of this context.
            _retain_candidate_pages(source, assessment, candidate)
            source["source_windows"] = window_observations(
                service.evidence, source["evidence"]
            )
            source = refresh_citation_contract(source)
        existing = window_observations(service.evidence, source["evidence"])
        seen = tuple(
            ReviewSourceWindow(
                file=w["file"], start_line=w["start_line"], end_line=w["end_line"]
            )
            for w in existing
        )
        plan = plan_gaps(
            assessment,
            service.evidence,
            seen,
            gap_history(previous),
            host_navigation=service.evidence.repository_obligations,
        )
        if not plan.gaps or (not plan.windows and previous):
            continue
        identifier = _begin_attempt(
            service, batch_id, assessment, remaining, round_number=len(previous) + 1
        )
        source, gaps, events = _acquire(service, source, plan)
        update_attempt(
            service,
            identifier,
            status="prepared" if events else "no_source_progress",
            evidence_gaps=[gap.model_dump(mode="json") for gap in gaps],
            source_events=events,
        )
        if events:
            return source, identifier
    return None


def _retain_candidate_pages(source, assessment, candidate):
    selected = source["targets"][0]
    seeds = [
        seed
        for seed in source.get("source_path_seeds", ())
        if seed["candidate_id"] == candidate
    ]
    chosen = set(selected.get("evidence_ids", ())) | {
        seed["evidence_id"] for seed in seeds
    }
    # The accepted assessment can cite independent evidence for and against
    # the candidate even when the final verdict still needs another fact.
    chosen.update(
        str(identifier)
        for field in ("evidence_ids", "counterevidence_ids")
        for identifier in assessment.get(field, ())
    )
    chosen.update(
        str(identifier)
        for premise in assessment.get("premises", ())
        for identifier in premise.get("evidence_ids", ())
    )
    chosen.update(
        str(identifier)
        for obligation in assessment.get("host_obligations", ())
        for field in ("evidence_ids", "counterevidence_ids")
        for identifier in obligation.get(field, ())
    )
    source["evidence"] = [row for row in source["evidence"] if row["id"] in chosen]
    source["source_path_seeds"] = seeds


def _acquire(service, context, plan):
    by_id = {gap.gap_id: gap for gap in plan.gaps}
    events = []
    maximum = service.inputs.max_context_chars
    for identifier, window in plan.windows:
        service.repository.active(service.execution_id)
        gap = by_id[identifier]
        try:
            page = service.evidence.read(**window.model_dump())
            proposal = {**context, "evidence": [*context["evidence"], page]}
            proposal["source_windows"] = window_observations(
                service.evidence, proposal["evidence"]
            )
            context = _pack(proposal, maximum)
        except AuditError as error:
            if error.code in {"identity_error", "integrity_error"}:
                raise
            by_id[identifier] = _failure(gap, error.code)
            continue
        except (OSError, UnicodeError):
            by_id[identifier] = _failure(gap, "source_unavailable")
            continue
        updated = ReviewEvidenceGap.model_validate(
            {
                **gap.model_dump(),
                "status": "found",
                "failure_reason": None,
                "evidence_refs": (*gap.evidence_refs, page["id"]),
            }
        )
        by_id[identifier] = updated
        events.append(
            {
                **window.model_dump(),
                "status": "supplied",
                "gap_id": identifier,
                "evidence_id": page["id"],
                "origin": "repository_locator",
            }
        )
    return (
        refresh_citation_contract(refresh_control_context(service, context)),
        tuple(by_id.values()),
        events,
    )


def _failure(gap, reason):
    if gap.status == "found":
        return gap
    return gap.model_copy(update={"status": "blocked", "failure_reason": reason})
