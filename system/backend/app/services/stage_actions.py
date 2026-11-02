"""Explicit approval and retry transitions shared by interactive adapters."""

from datetime import timedelta

from sqlalchemy import update
from sqlmodel import Session, select

from app.contracts.stages import FixtureApproval
from app.domain.audit import AuditError
from app.models import get_datetime_utc
from app.persistence.knowledge_models import RuleVersion
from app.persistence.stage_models import StageRun
from app.services.stage_lifecycle import create_stage_run, owned_stage


def approve_stage(session: Session, identifier, owner_id, reason: str) -> StageRun:
    reason = FixtureApproval(reason=reason).reason
    stage = owned_stage(session, identifier, owner_id)
    rule = session.exec(
        select(RuleVersion).where(RuleVersion.stage_id == stage.id)
    ).first()
    if (
        stage.kind != "rule"
        or rule is None
        or rule.owner_id != owner_id
        or rule.audit_id != stage.audit_id
        or rule.status != "draft"
        or stage.status != "awaiting_confirmation"
    ):
        raise AuditError("当前规则不处于等待样本确认状态")
    result = session.execute(
        update(StageRun)
        .where(StageRun.id == stage.id, StageRun.status == "awaiting_confirmation")
        .values(status="queued", updated_at=get_datetime_utc())
    )
    if result.rowcount != 1:
        session.rollback()
        raise AuditError("样本确认已被其他请求处理")
    rule.fixtures_approved, rule.fixture_approval_reason = True, reason
    session.add(rule)
    session.commit()
    session.refresh(stage)
    return stage


def retry_stage(session: Session, identifier, owner_id) -> StageRun:
    previous = owned_stage(session, identifier, owner_id)
    if previous.status not in {"failed", "cancelled"}:
        raise AuditError("仅失败或取消阶段可创建重跑记录")
    inputs, initial_result = previous.inputs, None
    if previous.kind == "scout" and inputs.get("continuation_from_id"):
        from app.services.scout_continuation import continuation_inputs
        from app.services.stage_lifecycle import owned_audit

        audit = owned_audit(session, previous.audit_id, owner_id)
        inputs, initial_result = continuation_inputs(previous, audit, session)
    # Retry is a new execution with the original experiment policy, not today's
    # implicit defaults. Receipts, call usage and checkpoints belong to the old ID.
    return create_stage_run(
        session,
        previous.audit_id,
        owner_id,
        previous.kind,
        inputs,
        initial_result=initial_result,
        prompt_version=previous.prompt_version,
        policy=previous.model_config_snapshot,
    )


def cancel_stage(session: Session, identifier, owner_id) -> StageRun:
    owned_stage(session, identifier, owner_id)
    stage = session.exec(
        select(StageRun).where(StageRun.id == identifier).with_for_update()
    ).one()
    if stage.status not in {"queued", "running", "awaiting_confirmation"}:
        raise AuditError("阶段当前不能取消")
    stage.status, stage.phase = "cancelled", "cancel_requested"
    stage.updated_at = get_datetime_utc()
    session.add(stage)
    session.commit()
    session.refresh(stage)
    return stage


def recover_stage(session: Session, identifier, owner_id) -> StageRun:
    owned_stage(session, identifier, owner_id)
    stage = session.exec(
        select(StageRun).where(StageRun.id == identifier).with_for_update()
    ).one()
    if stage.status != "running" or stage.updated_at > get_datetime_utc() - timedelta(
        minutes=45
    ):
        raise AuditError("仅超过 45 分钟无更新的运行记录可标记失联")
    stage.status, stage.error = (
        "cancelled",
        "执行失联已回收；旧记录保留，可创建独立重试",
    )
    stage.updated_at = get_datetime_utc()
    session.add(stage)
    session.commit()
    session.refresh(stage)
    return stage
