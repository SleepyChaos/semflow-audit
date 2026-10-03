"""Versioned knowledge and rules; unpublished rules never enter default scanning."""

from datetime import datetime
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Column, DateTime
from sqlmodel import Field, SQLModel

from app.models import get_datetime_utc


class KnowledgeChunk(SQLModel, table=True):
    __tablename__ = "knowledge_chunk"
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    owner_id: UUID | None = Field(default=None, foreign_key="user.id", index=True)
    document_id: UUID
    version: str
    title: str
    source: str
    language: str
    position: int
    content: str
    digest: str
    embedding: list[float] | None = Field(
        default=None, sa_column=Column(Vector(), nullable=True)
    )
    embedding_model: str | None = None
    embedding_error: str | None = None
    created_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )


class RuleVersion(SQLModel, table=True):
    __tablename__ = "rule_version"
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    owner_id: UUID = Field(foreign_key="user.id", index=True)
    audit_id: UUID = Field(foreign_key="audit_run.id")
    stage_id: UUID = Field(foreign_key="stage_run.id", index=True)
    language: str
    title: str
    strategy: str
    query: str
    modules: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    query_hash: str
    dependencies: dict = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=False)
    )
    retrieval: list[dict] = Field(
        default_factory=list, sa_column=Column(JSON, nullable=False)
    )
    fixtures: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    fixtures_approved: bool = False
    fixture_approval_reason: str | None = None
    validation: dict = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=False)
    )
    status: str = "draft"
    published_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    created_at: datetime = Field(
        default_factory=get_datetime_utc, sa_type=DateTime(timezone=True)
    )
