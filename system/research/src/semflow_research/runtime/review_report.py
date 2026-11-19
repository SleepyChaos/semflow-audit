"""Turn frozen review state into a candidate-level public result."""

from uuid import UUID

from semflow_contracts.review_handoff import (
    CandidateReviewAttempt,
    CandidateReviewReport,
    ReviewPremise,
)

_INTERRUPTED = {
    "budget_exhausted",
    "unit_budget",
    "timeout",
    "provider_error",
    "rate_limited",
    "no_progress",
}


def _execution_state(row, assessment, batches):
    cause = row["reason_code"]
    if assessment is not None:
        return "partial" if any(b.get("code") for b in batches) else "completed"
    if cause == "outside_batch_limit":
        return "not_scheduled"
    if cause in _INTERRUPTED:
        return "interrupted"
    if cause in {"assessment_rejected", "assessment_omitted"} or batches:
        return "failed"
    return "not_run"


def _evidence_state(accepted, row):
    if accepted is None:
        return "validation_failed" if row["rejected_reasons"] else "not_assessed"
    if accepted.conclusion in {"pending", "insufficient"}:
        return "unresolved"
    return "validated_references"


def _premises(raw, evidence_ref):
    for p in raw.get("premises", []):
        refs = tuple(
            evidence_ref(identifier) for identifier in p.get("evidence_ids", [])
        )
        quote = p.get("quote", "")
        status = p["status"]
        if status == "missing":
            verified = "unresolved"
        elif status in {"established", "contradicted"} and quote and refs:
            verified = "source_grounded"
        else:
            verified = "model_inference"
        yield ReviewPremise(
            role=p["premise"],
            status=status,
            explanation=p["reason"],
            policy_basis=p.get("policy_basis"),
            verification=verified,
            quote=quote,
            evidence_refs=refs,
        )


def build_report(context, raw, candidates, assessments, candidate_ref, evidence_ref):
    by_id = {str(row.candidate_id): row for row in candidates}
    accepted = {str(a.candidate_ref.entity_id): a for a in assessments}
    batch_by_id = {b["batch_id"]: b for b in raw.get("batches", [])}
    accepted_raw = {
        p["candidate_id"]: p
        for b in batch_by_id.values()
        for p in b.get("assessments", [])
    }
    records = []
    for handoff in raw["candidate_handoffs"]:
        identifier = handoff["candidate_id"]
        candidate = by_id[identifier]
        assessment = accepted.get(identifier)
        details = accepted_raw.get(identifier, {})
        batches = [batch_by_id[b] for b in handoff["batch_ids"]]
        records.append(
            CandidateReviewAttempt(
                candidate_ref=candidate_ref(UUID(identifier)),
                previous_candidate_ref=candidate.derived_from,
                source_type=handoff["origin"],
                location=candidate.primary_location,
                weakness=candidate.weakness,
                execution_state=_execution_state(handoff, assessment, batches),
                evidence_state=_evidence_state(assessment, handoff),
                assessment=assessment,
                stop_code=handoff["reason_code"],
                stop_detail=next(
                    (b.get("reason") for b in reversed(batches) if b.get("code")), None
                ),
                premises=tuple(_premises(details, evidence_ref)),
                evidence_gaps=tuple(handoff.get("evidence_gaps", ())),
                runtime_unknowns=tuple(handoff["runtime_unknowns"]),
                validation_errors=tuple(handoff["rejected_reasons"]),
                batch_ids=tuple(handoff["batch_ids"]),
                observed_source_windows=tuple(
                    handoff.get("observed_source_windows", ())
                ),
                next_action=handoff.get("next_action"),
            )
        )
    return CandidateReviewReport(
        execution_id=context.execution_id,
        snapshot_id=context.spec.source.snapshot_id,
        source_digest=context.spec.source.tree_sha256,
        records=tuple(records),
    )
