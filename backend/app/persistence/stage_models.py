"""Persistent stage histories, evidence, findings and human decisions."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, Column, DateTime
from sqlmodel import Field, SQLModel

from app.models import get_datetime_utc


class StageRun(SQLModel, table=True):
    __tablename__ = "stage_run"
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    audit_id: UUID = Field(foreign_key="audit_run.id", index=True)
    kind: str
    status: str = "queued"
    phase: str = "queued"
    inputs: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    result: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    error: str | None = None
    model: str | None = None
    prompt_version: str = "1"
    usage: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )


class Evidence(SQLModel, table=True):
    __tablename__ = "audit_evidence"
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    stage_id: UUID = Field(foreign_key="stage_run.id", index=True)
    audit_id: UUID = Field(foreign_key="audit_run.id", index=True)
    kind: str
    snapshot_hash: str
    reference: dict = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=False)
    )
    content: str
    digest: str
    created_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )


class Candidate(SQLModel, table=True):
    __tablename__ = "audit_candidate"
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    audit_id: UUID = Field(foreign_key="audit_run.id", index=True)
    stage_id: UUID = Field(foreign_key="stage_run.id", index=True)
    static_finding_id: str | None = None
    origin: str
    title: str
    description: str
    status: str = "pending"
    evidence_ids: list[str] = Field(
        default_factory=list, sa_column=Column(JSON, nullable=False)
    )
    related_target: str | None = None
    identity_key: str = ""
    novelty: str = "unknown"
    location: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )


class Decision(SQLModel, table=True):
    __tablename__ = "audit_decision"
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    candidate_id: UUID = Field(foreign_key="audit_candidate.id", index=True)
    actor_id: UUID = Field(foreign_key="user.id")
    status: str
    reason: str
    evidence_ids: list[str] = Field(
        default_factory=list, sa_column=Column(JSON, nullable=False)
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )


class RepairRecord(SQLModel, table=True):
    __tablename__ = "audit_repair"
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    stage_id: UUID = Field(foreign_key="stage_run.id", unique=True)
    audit_id: UUID = Field(foreign_key="audit_run.id", index=True)
    candidate_ids: list[str] = Field(
        default_factory=list, sa_column=Column(JSON, nullable=False)
    )
    changes: list[dict] = Field(
        default_factory=list, sa_column=Column(JSON, nullable=False)
    )
    validation: dict = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=False)
    )
    status: str = "draft"
    accepted_by: UUID | None = Field(default=None, foreign_key="user.id")
    acceptance_reason: str | None = None
