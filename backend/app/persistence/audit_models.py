import uuid
from datetime import datetime

from sqlalchemy import JSON, Column, DateTime
from sqlmodel import Field, SQLModel

from app.models import get_datetime_utc


class AuditRun(SQLModel, table=True):
    __tablename__ = "audit_run"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    owner_id: uuid.UUID = Field(foreign_key="user.id", index=True)
    project_name: str = Field(max_length=120)
    language: str
    status: str = "queued"
    phase: str = "queued"
    snapshot_hash: str
    query_pack: str
    source_run_id: uuid.UUID
    suite: str
    codeql_version: str | None = None
    error: str | None = None
    findings: list[dict] = Field(
        default_factory=list, sa_column=Column(JSON, nullable=False)
    )
    coverage: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )
