"""Internal algorithm state. Public JSON uses semflow_contracts codecs instead.

These records preserve algorithm feedback histories, not platform workflow state.
snapshot_id always identifies frozen source; execution_id identifies its producer.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field
from semflow_contracts.common import ArtifactRef, EntityRef


def get_datetime_utc():
    return datetime.now(UTC)


class ScientificRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=get_datetime_utc)


class SourceRecord(ScientificRecord):
    language: str
    snapshot_hash: str
    corpus_scope: UUID
    query_pack: str = ""
    suite: str = ""
    codeql_version: str | None = None
    findings: list[dict] = Field(default_factory=list)
    finding_refs: dict[str, ArtifactRef] = Field(default_factory=dict)
    finding_candidate_refs: dict[str, EntityRef] = Field(default_factory=dict)
    coverage: dict = Field(default_factory=dict)
    custom_rule_ids: list[str] = Field(default_factory=list)
    status: str = "completed"
    phase: str = "source_ready"

    @property
    def snapshot_id(self):
        return self.id


class ExecutionRecord(ScientificRecord):
    snapshot_id: UUID
    kind: str
    status: str = "queued"
    phase: str = "queued"
    inputs: dict = Field(default_factory=dict)
    result: dict = Field(default_factory=dict)
    error: str | None = None
    model: str | None = None
    method_version: str
    policy: dict = Field(default_factory=dict)
    usage: dict = Field(default_factory=dict)
    model_calls: list[dict] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=get_datetime_utc)


class Evidence(ScientificRecord):
    execution_id: UUID
    snapshot_id: UUID
    kind: str
    snapshot_hash: str
    reference: dict
    content: str
    digest: str
    provenance: dict = Field(default_factory=dict)


class Candidate(ScientificRecord):
    source_ref: EntityRef | None = None
    snapshot_id: UUID
    execution_id: UUID
    static_finding_id: str | None = None
    origin: str
    title: str
    description: str
    status: str = "pending"
    evidence_ids: list[str] = Field(default_factory=list)
    related_target: str | None = None
    identity_key: str = ""
    novelty: str = "unknown"
    weakness: str = "unknown"
    model_assessment: str = "unknown"
    location: dict = Field(default_factory=dict)


class Decision(ScientificRecord):
    candidate_id: UUID
    actor_id: str
    actor_kind: str
    status: str
    reason: str
    evidence_ids: list[str]


class RepairRecord(ScientificRecord):
    execution_id: UUID
    snapshot_id: UUID
    candidate_ids: list[str]
    changes: list[dict] = Field(default_factory=list)
    validation: dict = Field(default_factory=dict)
    status: str = "draft"


class RuleVersion(ScientificRecord):
    execution_id: UUID
    snapshot_id: UUID
    corpus_scope: UUID
    language: str
    title: str
    purpose: str
    holdout_id: str | None = None
    strategy: str
    query: str
    modules: dict = Field(default_factory=dict)
    query_hash: str
    dependencies: dict
    retrieval: list[dict] = Field(default_factory=list)
    fixtures: dict
    fixtures_approved: bool = False
    fixture_approval_reason: str | None = None
    validation: dict = Field(default_factory=dict)
    status: str = "draft"


class KnowledgeChunk(ScientificRecord):
    corpus_scope: UUID
    document_id: UUID
    version: str
    title: str
    source: str
    language: str
    position: int
    content: str
    digest: str
    provenance: dict
    corpus: str
    embedding: list[float] | None = None
    embedding_model: str | None = None
    embedding_identity: str | None = None
