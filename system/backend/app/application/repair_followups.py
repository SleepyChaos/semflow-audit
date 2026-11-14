"""Deliver committed platform follow-ups without re-entering a repair algorithm."""

import logging
from datetime import timedelta
from uuid import UUID

from sqlmodel import Session, select

from app.application.stage_dispatch import StagePublisher, dispatch_stage
from app.core.db import engine
from app.domain.audit import AuditError
from app.models import get_datetime_utc
from app.persistence.audit_models import AuditRun
from app.persistence.stage_models import StageFollowup, StageRun
from app.services.stage_lifecycle import create_stage_run

logger = logging.getLogger(__name__)


def _claim(source_stage_id: UUID):
    with Session(engine) as session:
        row = session.exec(
            select(StageFollowup)
            .where(StageFollowup.source_stage_id == source_stage_id)
            .with_for_update()
        ).first()
        now = get_datetime_utc()
        if row is None or row.status in {"delivered", "failed"}:
            return None
        if row.status == "processing" and row.lease_until and row.lease_until > now:
            return None
        row.status, row.lease_until = "processing", now + timedelta(minutes=5)
        row.attempts += 1
        row.updated_at = now
        session.add(row)
        session.commit()
        session.refresh(row)
        return row.id, row.attempts


def _existing_target(session: Session, row: StageFollowup, source: StageRun):
    targets = session.exec(
        select(StageRun).where(
            StageRun.audit_id == source.audit_id, StageRun.kind == "verification"
        )
    ).all()
    return next(
        (stage for stage in targets if stage.inputs.get("followup_id") == str(row.id)),
        None,
    )


def _target(followup_id: UUID, attempt: int) -> StageRun:
    with Session(engine) as session:
        row = session.exec(
            select(StageFollowup)
            .where(StageFollowup.id == followup_id)
            .with_for_update()
        ).one()
        if row.status != "processing" or row.attempts != attempt:
            raise AuditError("后续任务租约已转移", code="followup_lease_lost")
        source = session.get(StageRun, row.source_stage_id)
        if (
            source is None
            or source.status != "completed"
            or source.kind != "repair"
            or source.result.get("repair_id") != str(row.repair_id)
            or source.inputs.get("verification_suite_id") != str(row.suite_id)
        ):
            raise AuditError("修复完成记录与后续验证意图不一致")
        # The source lock serializes target creation, including crash recovery
        # after create_stage_run committed but before the outbox pointer was saved.
        session.exec(
            select(StageRun).where(StageRun.id == source.id).with_for_update()
        ).one()
        target = _existing_target(session, row, source)
        if target is None:
            audit = session.get(AuditRun, source.audit_id)
            target = create_stage_run(
                session,
                source.audit_id,
                audit.owner_id,
                "verification",
                {
                    "repair_id": str(row.repair_id),
                    "suite_id": str(row.suite_id),
                    "followup_id": str(row.id),
                },
            )
        elif (target.inputs.get("repair_id"), target.inputs.get("suite_id")) != (
            str(row.repair_id),
            str(row.suite_id),
        ):
            raise AuditError("后续验证任务的输入身份发生变化")
        row = session.get(StageFollowup, followup_id)
        row.target_stage_id = target.id
        session.add(row)
        session.commit()
        session.refresh(target)
        session.expunge(target)
        return target


def _finish(followup_id: UUID, attempt: int, target: StageRun) -> None:
    with Session(engine) as session:
        row = session.exec(
            select(StageFollowup)
            .where(StageFollowup.id == followup_id)
            .with_for_update()
        ).one()
        if row.attempts != attempt or row.status != "processing":
            return
        target = session.get(StageRun, target.id)
        row.target_stage_id = target.id
        row.status = "failed" if target.status == "failed" else "delivered"
        row.error, row.lease_until, row.updated_at = (
            target.error,
            None,
            get_datetime_utc(),
        )
        session.add(row)
        session.commit()


def _failure(followup_id: UUID, attempt: int) -> StageRun | None:
    with Session(engine) as session:
        row = session.exec(
            select(StageFollowup)
            .where(StageFollowup.id == followup_id)
            .with_for_update()
        ).one()
        if row.attempts != attempt or row.status != "processing":
            return None
        source = session.get(StageRun, row.source_stage_id)
        target = (
            session.get(StageRun, row.target_stage_id) if row.target_stage_id else None
        )
        if target is None:
            target = _existing_target(session, row, source)
        if target is None:
            # It is a separate failed execution, never a rewrite of the repair.
            target = StageRun(
                audit_id=source.audit_id,
                kind="verification",
                status="failed",
                phase="verification_not_started",
                inputs={
                    "repair_id": str(row.repair_id),
                    "suite_id": str(row.suite_id),
                    "followup_id": str(row.id),
                },
                error="自动前后对比未启动，请查看测试目标与任务队列后重新运行；已生成补丁保留。",
            )
            session.add(target)
            session.flush()
        row.target_stage_id = target.id
        row.status = "failed" if target.status == "failed" else "pending"
        row.error, row.lease_until, row.updated_at = (
            target.error,
            None,
            get_datetime_utc(),
        )
        session.add(row)
        session.commit()
        session.refresh(target)
        session.expunge(target)
        return target


def deliver_repair_followup(
    source_stage_id: UUID | str,
    *,
    publisher: StagePublisher | None = None,
) -> StageRun | None:
    claimed = _claim(UUID(str(source_stage_id)))
    if claimed is None:
        return None
    followup_id, attempt = claimed
    try:
        target = _target(followup_id, attempt)
        with Session(engine) as session:
            current = session.get(StageRun, target.id)
            dispatch_stage(current, session, publisher=publisher)
            session.expunge(current)
        _finish(followup_id, attempt, current)
        return current
    except AuditError as exc:
        if exc.code == "stage_busy":
            with Session(engine) as session:
                row = session.exec(
                    select(StageFollowup)
                    .where(StageFollowup.id == followup_id)
                    .with_for_update()
                ).one()
                if row.attempts == attempt and row.status == "processing":
                    row.status, row.error, row.lease_until = "pending", str(exc), None
                    session.add(row)
                    session.commit()
            return None
        logger.exception("Repair follow-up failed: %s", source_stage_id)
        return _failure(followup_id, attempt)
    except Exception:
        logger.exception("Repair follow-up failed: %s", source_stage_id)
        return _failure(followup_id, attempt)


def reconcile_followups(
    *, publisher: StagePublisher | None = None, limit: int = 100
) -> int:
    now = get_datetime_utc()
    with Session(engine) as session:
        rows = session.exec(
            select(StageFollowup.source_stage_id)
            .where(
                (StageFollowup.status == "pending")
                | (
                    (StageFollowup.status == "processing")
                    & (StageFollowup.lease_until < now)
                )
            )
            .limit(limit)
        ).all()
    return sum(
        deliver_repair_followup(identifier, publisher=publisher) is not None
        for identifier in rows
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    reconcile_followups()
