"""Platform-owned execution binding; absence means historical legacy executor."""

from uuid import UUID, uuid4

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class ResearchBinding(SQLModel, table=True):
    __tablename__ = "research_binding"
    execution_id: UUID = Field(default_factory=uuid4, primary_key=True)
    stage_id: UUID = Field(
        foreign_key="stage_run.id", ondelete="CASCADE", unique=True, index=True
    )
    # Peer: repair_check_views / repair_projection / repair_integrity.
    # AGENT: /1 retains the historical syntax-slice codec; /2 freezes the full
    # native verification view with explicit legacy/scientific hash conversion.
    # Never reinterpret an already published binding using a different codec.
    executor: str = "semflow-research/1"
    # Peer: requests.freeze_stage -> runtime.execute_bound. AGENT: never rebuild
    # a bound request from current platform defaults; retry creates a new binding.
    request: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    resources: dict = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=False)
    )
    legacy_source_digest: str = ""
    manifest: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    # Peer: projection.project -> API candidate/evidence DTO readers. Keys are
    # research producer UUID/entity UUID, values platform UUIDs scoped to stage.
    # AGENT: change mapping and every nested DTO reference together; never reuse
    # a research UUID as the platform identity or overwrite human decisions.
    entity_map: dict[str, str] = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=False)
    )


class ResearchAuditBinding(SQLModel, table=True):
    """New scan binding; historical unbound audits retain their old executor."""

    __tablename__ = "research_audit_binding"
    execution_id: UUID = Field(default_factory=uuid4, primary_key=True)
    audit_id: UUID = Field(
        foreign_key="audit_run.id", ondelete="CASCADE", unique=True, index=True
    )
    scout_stage_id: UUID | None = Field(
        default=None, foreign_key="stage_run.id", ondelete="SET NULL"
    )
    policy: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    request: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    resources: dict = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=False)
    )
    legacy_source_digest: str = ""
    manifest: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    entity_map: dict[str, str] = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=False)
    )
