"""Automatic source-validated classification with explicit human overrides."""

from sqlmodel import select

from app.domain.audit import AuditError
from app.persistence.stage_models import Candidate, Decision, StageRun

STATUSES = {
    "supported": "confirmed",
    "excluded": "excluded",
    "pending": "insufficient",
    "insufficient": "insufficient",
}


def apply_model_classification(candidate, assessment, session):
    override = session.exec(
        select(Decision).where(Decision.candidate_id == candidate.id)
    ).first()
    if not override:
        candidate.status = STATUSES[assessment]


def change_classification(candidate, status, actor_id, session):
    current = session.exec(
        select(Candidate).where(Candidate.id == candidate.id).with_for_update()
    ).one()
    stage = session.get(StageRun, current.stage_id)
    if stage.status in {"queued", "running"}:
        raise AuditError("请等待当前复核结束后调整分类")
    labels = {
        "confirmed": "确认真实",
        "excluded": "确认误报",
        "insufficient": "证据不足",
    }
    decision = Decision(
        candidate_id=current.id,
        actor_id=actor_id,
        status=status,
        reason=f"人工调整评价分类：{labels[status]}；未填写额外判断理由。",
        evidence_ids=current.evidence_ids,
    )
    current.status = status
    session.add(current)
    session.add(decision)
    session.commit()
    session.refresh(decision)
    return decision


def classification_view(candidate, review, latest_decision):
    source = (
        "human"
        if latest_decision
        else "ai"
        if review and review["evaluated"]
        else "pending"
    )
    status = (
        candidate.status
        if latest_decision
        else STATUSES.get(review["status"], "pending")
        if review
        else "pending"
    )
    return {
        "status": status,
        "source": source,
        "updated_at": latest_decision.created_at.isoformat()
        if latest_decision
        else review.get("updated_at")
        if review
        else None,
    }
