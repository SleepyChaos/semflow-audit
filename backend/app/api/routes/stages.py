"""Owned stage execution, immutable histories and human evidence-based confirmation."""

from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, HTTPException
from sqlmodel import select

from app.api.deps import CurrentUser, SessionDep
from app.api.routes.audits import owned_run
from app.contracts.stages import (
    DecisionRequest,
    RepairRequest,
    ReviewRequest,
    RuleRequest,
)
from app.domain.audit import AuditError
from app.jobs.stages import execute_stage
from app.models import get_datetime_utc
from app.persistence.audit_models import AuditRun
from app.persistence.stage_models import Candidate, Decision, Evidence, StageRun
from app.services.evidence import EvidenceService, valid_evidence

router = APIRouter(tags=["stages"])


def owned_stage(identifier: UUID, session: SessionDep, user: CurrentUser) -> StageRun:
    stage = session.get(StageRun, identifier)
    if stage is None:
        raise HTTPException(404, "阶段执行不存在")
    owned_run(stage.audit_id, session, user)
    return stage


def dispatch_stage(stage: StageRun, session: SessionDep, resume: bool = False):
    try:
        execute_stage.delay(str(stage.id), resume)
    except Exception:
        stage.status, stage.error = "failed", "阶段任务队列不可用，请恢复后创建新的执行"
        session.add(stage)
        session.commit()
    session.refresh(stage)


def create_stage(
    audit_id: UUID, kind: str, inputs: dict, session: SessionDep, user: CurrentUser
):
    owned_run(audit_id, session, user)
    run = session.exec(
        select(AuditRun).where(AuditRun.id == audit_id).with_for_update()
    ).one()
    if kind not in {"review", "repair", "rule"}:
        raise HTTPException(409, "此记录不支持后台重跑")
    if run.status != "completed":
        raise HTTPException(409, "需要先完成静态审计")
    active = session.exec(
        select(StageRun).where(
            StageRun.audit_id == audit_id,
            StageRun.kind == kind,
            StageRun.status.in_(["queued", "running"]),
        )
    ).first()
    if active:
        raise HTTPException(409, "该阶段已有正在执行的任务")
    stage = StageRun(audit_id=audit_id, kind=kind, inputs=inputs)
    session.add(stage)
    session.commit()
    session.refresh(stage)
    dispatch_stage(stage, session)
    return stage


@router.get("/audits/{audit_id}/stages")
def stages(audit_id: UUID, session: SessionDep, user: CurrentUser):
    owned_run(audit_id, session, user)
    return session.exec(
        select(StageRun)
        .where(StageRun.audit_id == audit_id)
        .order_by(StageRun.created_at.desc())
    ).all()


@router.post("/audits/{audit_id}/review", status_code=201)
def review(audit_id: UUID, body: ReviewRequest, session: SessionDep, user: CurrentUser):
    return create_stage(audit_id, "review", body.model_dump(mode="json"), session, user)


@router.post("/audits/{audit_id}/repair", status_code=201)
def repair(audit_id: UUID, body: RepairRequest, session: SessionDep, user: CurrentUser):
    owned_run(audit_id, session, user)
    candidates = session.exec(
        select(Candidate).where(
            Candidate.audit_id == audit_id, Candidate.id.in_(body.candidate_ids)
        )
    ).all()
    if len(candidates) != len(set(body.candidate_ids)) or any(
        row.status != "confirmed" for row in candidates
    ):
        raise HTTPException(409, "请选择本次审计中人工确认的缺陷")
    return create_stage(audit_id, "repair", body.model_dump(mode="json"), session, user)


@router.post("/audits/{audit_id}/rule", status_code=201)
def rule(audit_id: UUID, body: RuleRequest, session: SessionDep, user: CurrentUser):
    return create_stage(audit_id, "rule", body.model_dump(mode="json"), session, user)


@router.get("/stages/{identifier}")
def stage_detail(identifier: UUID, session: SessionDep, user: CurrentUser):
    return owned_stage(identifier, session, user)


@router.get("/stages/{identifier}/evidence")
def evidence(identifier: UUID, session: SessionDep, user: CurrentUser):
    owned_stage(identifier, session, user)
    return session.exec(select(Evidence).where(Evidence.stage_id == identifier)).all()


@router.post("/stages/{identifier}/retry", status_code=201)
def retry(identifier: UUID, session: SessionDep, user: CurrentUser):
    previous = owned_stage(identifier, session, user)
    if previous.status not in {"failed", "cancelled"}:
        raise HTTPException(409, "仅失败或取消阶段可创建重跑记录")
    return create_stage(
        previous.audit_id, previous.kind, previous.inputs, session, user
    )


@router.post("/stages/{identifier}/cancel")
def cancel(identifier: UUID, session: SessionDep, user: CurrentUser):
    owned_stage(identifier, session, user)
    stage = session.exec(
        select(StageRun).where(StageRun.id == identifier).with_for_update()
    ).one()
    if stage.status not in {"queued", "running", "awaiting_confirmation"}:
        raise HTTPException(409, "阶段当前不能取消")
    stage.status, stage.phase = "cancelled", "cancel_requested"
    stage.updated_at = get_datetime_utc()
    session.add(stage)
    session.commit()
    return {
        "status": "cancelled",
        "meaning": "当前外部调用完成后停止，原始快照不受影响",
    }


@router.post("/stages/{identifier}/recover")
def recover(identifier: UUID, session: SessionDep, user: CurrentUser):
    owned_stage(identifier, session, user)
    stage = session.exec(
        select(StageRun).where(StageRun.id == identifier).with_for_update()
    ).one()
    if stage.status != "running" or stage.updated_at > get_datetime_utc() - timedelta(
        minutes=45
    ):
        raise HTTPException(409, "仅超过 45 分钟无更新的运行记录可标记失联")
    stage.status, stage.error = (
        "cancelled",
        "执行失联已回收；旧记录保留，可创建独立重试",
    )
    stage.updated_at = get_datetime_utc()
    session.add(stage)
    session.commit()
    session.refresh(stage)
    return stage


@router.get("/audits/{audit_id}/candidates")
def candidates(audit_id: UUID, session: SessionDep, user: CurrentUser):
    owned_run(audit_id, session, user)
    return session.exec(
        select(Candidate)
        .where(Candidate.audit_id == audit_id)
        .order_by(Candidate.created_at)
    ).all()


@router.get("/candidates/{identifier}/decisions")
def decisions(identifier: UUID, session: SessionDep, user: CurrentUser):
    candidate = session.get(Candidate, identifier)
    if candidate is None:
        raise HTTPException(404, "候选不存在")
    owned_run(candidate.audit_id, session, user)
    return session.exec(
        select(Decision)
        .where(Decision.candidate_id == identifier)
        .order_by(Decision.created_at)
    ).all()


@router.post("/candidates/{identifier}/decisions", status_code=201)
def decide(
    identifier: UUID, body: DecisionRequest, session: SessionDep, user: CurrentUser
):
    candidate = session.get(Candidate, identifier)
    if candidate is None:
        raise HTTPException(404, "候选不存在")
    owned_run(candidate.audit_id, session, user)
    stage = session.get(StageRun, candidate.stage_id)
    if stage.status in {"queued", "running"}:
        raise HTTPException(409, "请等待复审结束后记录人工判断")
    try:
        valid_evidence(
            candidate.audit_id,
            body.evidence_ids,
            body.status in {"confirmed", "excluded"},
        )
    except AuditError as exc:
        raise HTTPException(422, str(exc))
    decision = Decision(
        candidate_id=identifier,
        actor_id=user.id,
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


@router.post("/audits/{audit_id}/evidence", status_code=201)
def manual_evidence(
    audit_id: UUID,
    file: str,
    session: SessionDep,
    user: CurrentUser,
    start_line: int = 1,
    end_line: int = 40,
):
    owned_run(audit_id, session, user)
    stage = StageRun(
        audit_id=audit_id,
        kind="manual_evidence",
        status="completed",
        phase="human_evidence",
    )
    session.add(stage)
    session.commit()
    session.refresh(stage)
    try:
        return EvidenceService(str(audit_id), str(stage.id), []).read(
            file, start_line, end_line
        )
    except AuditError as exc:
        stage.status, stage.error = "failed", str(exc)
        session.add(stage)
        session.commit()
        raise HTTPException(422, str(exc))


@router.get("/audits/{audit_id}/evidence")
def all_evidence(audit_id: UUID, session: SessionDep, user: CurrentUser):
    owned_run(audit_id, session, user)
    return session.exec(
        select(Evidence)
        .where(Evidence.audit_id == audit_id)
        .order_by(Evidence.created_at.desc())
        .limit(300)
    ).all()


@router.get("/stages/{identifier}/logs")
def stage_logs(identifier: UUID, session: SessionDep, user: CurrentUser):
    owned_stage(identifier, session, user)
    from app.adapters.artifacts import ArtifactStore

    return {"text": ArtifactStore().log_tail(str(identifier))}
