from uuid import UUID

from sqlalchemy import update
from sqlmodel import Session, select

from app.core.db import engine
from app.domain.audit import AuditError
from app.models import get_datetime_utc
from app.persistence.stage_models import StageRun


class StageCancelled(AuditError):
    pass


class StageRepository:
    def get(self, identifier: str) -> StageRun:
        with Session(engine) as session:
            stage = session.get(StageRun, UUID(identifier))
            if stage is None:
                raise AuditError("阶段不存在")
            session.expunge(stage)
            return stage

    def claim(self, identifier: str) -> bool:
        with Session(engine) as session:
            result = session.execute(
                update(StageRun)
                .where(StageRun.id == UUID(identifier), StageRun.status == "queued")
                .values(status="running", updated_at=get_datetime_utc())
            )
            session.commit()
            return result.rowcount == 1

    def update(self, identifier: str, **values) -> None:
        with Session(engine) as session:
            stage = session.exec(
                select(StageRun)
                .where(StageRun.id == UUID(identifier))
                .with_for_update()
            ).one()
            if stage.status == "cancelled":
                raise StageCancelled("阶段已取消")
            for key, value in values.items():
                setattr(stage, key, value)
            stage.updated_at = get_datetime_utc()
            session.add(stage)
            session.commit()

    def active(self, identifier: str) -> None:
        if self.get(identifier).status == "cancelled":
            raise StageCancelled("阶段已取消")
