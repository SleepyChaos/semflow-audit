"""Stage delivery policy independent of HTTP request/response objects."""

from collections.abc import Callable

from sqlmodel import Session

from app.persistence.stage_models import StageRun

StagePublisher = Callable[[str, bool], None]


def celery_publisher(stage_id: str, resume: bool) -> None:
    from app.jobs.stages import execute_stage

    execute_stage.delay(stage_id, resume)


def dispatch_stage(
    stage: StageRun,
    session: Session,
    resume: bool = False,
    *,
    publisher: StagePublisher | None = None,
) -> None:
    """Delivery failure must not overwrite a task already claimed by a worker."""
    if stage.status != "queued":
        return
    try:
        (publisher or celery_publisher)(str(stage.id), resume)
    except Exception:
        from sqlalchemy import update

        session.execute(
            update(StageRun)
            .where(StageRun.id == stage.id, StageRun.status == "queued")
            .values(status="failed", error="阶段任务队列不可用，请恢复后创建新的执行")
        )
        session.commit()
    session.refresh(stage)
