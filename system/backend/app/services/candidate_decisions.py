"""Human candidate decisions require real evidence from the owned source snapshot."""

from sqlmodel import Session

from app.contracts.stages import DecisionRequest
from app.domain.audit import AuditError
from app.persistence.stage_models import Candidate, Decision, StageRun
from app.services.evidence import valid_evidence
from app.services.stage_lifecycle import owned_audit


def record_decision(session: Session, identifier, owner_id, body: DecisionRequest):
    candidate = session.get(Candidate, identifier)
    if candidate is None:
        raise AuditError("候选不存在", code="not_found")
    owned_audit(session, candidate.audit_id, owner_id)
    stage = session.get(StageRun, candidate.stage_id)
    if stage.status in {"queued", "running"}:
        raise AuditError("请等待复审结束后记录人工判断")
    try:
        valid_evidence(
            candidate.audit_id,
            body.evidence_ids,
            body.status in {"confirmed", "excluded"},
        )
    except AuditError as exc:
        raise AuditError(str(exc), code="invalid_input") from exc
    decision = Decision(
        candidate_id=identifier,
        actor_id=owner_id,
        status=body.status,
        reason=body.reason,
        evidence_ids=list(map(str, body.evidence_ids)),
    )
    candidate.status = body.status
    if body.evidence_ids:
        candidate.evidence_ids = list(map(str, body.evidence_ids))
    session.add(candidate)
    session.add(decision)
    session.commit()
    session.refresh(decision)
    return decision
