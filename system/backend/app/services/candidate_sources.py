"""Human-selected source is attached explicitly, never via a global evidence list."""

from sqlmodel import select

from app.domain.audit import AuditError
from app.persistence.stage_models import Candidate, StageRun
from app.services.evidence import EvidenceService


def supplement_source(candidate, file, line, session):
    original = session.get(StageRun, candidate.stage_id)
    if original.status in {"queued", "running"}:
        raise AuditError("请等待当前复核结束后补充人工证据")
    stage = StageRun(
        audit_id=candidate.audit_id, kind="manual_evidence", phase="human_evidence"
    )
    session.add(stage)
    session.commit()
    session.refresh(stage)
    try:
        evidence = EvidenceService(str(candidate.audit_id), str(stage.id), []).read(
            file, max(1, line - 5), line + 10
        )
    except (AuditError, OSError, ValueError) as exc:
        stage.status, stage.error = "failed", str(exc)
        session.add(stage)
        session.commit()
        raise
    current = session.exec(
        select(Candidate).where(Candidate.id == candidate.id).with_for_update()
    ).one()
    current.evidence_ids = list(dict.fromkeys([*current.evidence_ids, evidence["id"]]))
    stage.status = "completed"
    stage.result = {"candidate_id": str(candidate.id), "evidence_id": evidence["id"]}
    session.add(current)
    session.add(stage)
    session.commit()
    return evidence
