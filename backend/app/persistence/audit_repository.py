from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import update
from sqlmodel import Session

from app.core.db import engine
from app.persistence.audit_models import AuditRun


class AuditRepository:
    def get(self, run_id: str) -> AuditRun:
        with Session(engine) as session:
            run = session.get(AuditRun, UUID(run_id))
            if run is None:
                raise ValueError("Audit run not found")
            session.expunge(run)
            return run

    def claim(self, run_id: str) -> bool:
        with Session(engine) as session:
            result = session.execute(
                update(AuditRun)
                .where(AuditRun.id == UUID(run_id), AuditRun.status == "queued")
                .values(status="running", updated_at=datetime.now(UTC))
            )
            session.commit()
            return result.rowcount == 1

    def update(self, run_id: str, **changes: object) -> None:
        with Session(engine) as session:
            run = session.get(AuditRun, UUID(run_id))
            if run is None:
                raise ValueError("Audit run not found")
            for key, value in changes.items():
                setattr(run, key, value)
            run.updated_at = datetime.now(UTC)
            session.add(run)
            session.commit()
