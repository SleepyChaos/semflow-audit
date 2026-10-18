"""Shared candidate projections for the workbench, reports and evidence reader."""

from sqlmodel import select

from app.persistence.stage_models import Candidate, Decision, Evidence, StageRun
from app.services.candidate_classification import classification_view
from app.services.candidate_groups import project_candidates
from app.services.candidate_reviews import candidate_review


def present_candidates(
    rows, stages, decisions, audit, *, grouped=False, localize=False, evidence=()
):
    by_stage = {stage.id: stage for stage in stages}
    latest = {row.candidate_id: row for row in decisions}
    payloads = []
    for row in rows:
        review = candidate_review(row, by_stage, audit.snapshot_hash)
        payload = {
            **row.model_dump(mode="json"),
            "review": review,
            "classification": classification_view(row, review, latest.get(row.id)),
            "evidence_ids": review["evidence_ids"] if review else row.evidence_ids,
        }
        if localize:
            from app.services.candidate_localization import localized_view

            payload = localized_view(payload, by_stage)
        payloads.append(payload)
    return (
        project_candidates(
            payloads, stages, audit.snapshot_hash, evidence, audit.language
        )
        if grouped
        else payloads
    )


def candidate_views(session, audit, *, grouped=False):
    rows = session.exec(
        select(Candidate)
        .where(Candidate.audit_id == audit.id)
        .order_by(Candidate.created_at)
    ).all()
    stages = session.exec(select(StageRun).where(StageRun.audit_id == audit.id)).all()
    decisions = session.exec(
        select(Decision)
        .join(Candidate, Candidate.id == Decision.candidate_id)
        .where(Candidate.audit_id == audit.id)
        .order_by(Decision.created_at)
    ).all()
    from app.services.result_explanations import explain_candidate

    evidence = session.exec(select(Evidence).where(Evidence.audit_id == audit.id)).all()
    material = [row.model_dump(mode="json") for row in evidence]
    result = present_candidates(
        rows,
        stages,
        decisions,
        audit,
        grouped=grouped,
        localize=True,
        evidence=material,
    )
    return [{**row, "explanation": explain_candidate(row, material)} for row in result]
