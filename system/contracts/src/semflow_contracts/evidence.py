"""Evidence and caller decisions carry research identities, never ORM objects."""

from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, ConfigDict, Field, model_validator

from semflow_contracts.common import (
    ArtifactRef,
    BundleRef,
    Contract,
    Digest,
    EntityRef,
    SourceLocation,
)
from semflow_contracts.wire import schema_meaning


class EvidenceProvenance(Contract):
    producer: str = Field(min_length=1)
    tool_version: str | None = None
    call_id: UUID | None = None
    input_refs: tuple[ArtifactRef, ...] = ()


class EvidenceRecord(Contract):
    model_config = ConfigDict(json_schema_extra=schema_meaning("evidence"))

    evidence_id: UUID
    execution_id: UUID
    snapshot_id: UUID
    kind: Literal["code", "query", "tool", "knowledge"]
    content: ArtifactRef
    digest: Digest
    location: SourceLocation | None = None
    provenance: EvidenceProvenance

    @model_validator(mode="after")
    def identity(self):
        if self.content.owner_execution_id != self.execution_id:
            raise ValueError("Evidence content belongs to a different execution")
        if self.content.sha256 != self.digest:
            raise ValueError("Evidence digest does not match its content")
        if self.kind == "code" and self.location is None:
            raise ValueError("Code evidence requires a source location")
        if self.location is not None and (
            self.location.snapshot_id != self.snapshot_id
            or self.location.end_line < self.location.start_line
        ):
            raise ValueError("Evidence source identity or range is invalid")
        if self.kind in {"query", "tool"} and self.provenance.call_id is None:
            raise ValueError("Tool evidence requires an actual call identity")
        return self


class ActorRef(Contract):
    kind: Literal["human", "experiment_fixture"]
    id: str = Field(min_length=1)
    provenance: ArtifactRef | None = None

    @model_validator(mode="after")
    def fixture_provenance(self):
        if self.kind == "experiment_fixture" and self.provenance is None:
            raise ValueError("Experiment decisions require protocol provenance")
        return self


class DecisionRecord(Contract):
    decision_id: UUID
    target: EntityRef
    snapshot_id: UUID
    status: Literal["confirmed", "excluded", "pending", "insufficient"]
    actor: ActorRef
    reason: str = Field(min_length=10, max_length=4000)
    evidence_refs: tuple[EntityRef, ...] = ()
    created_at: AwareDatetime

    @model_validator(mode="after")
    def evidence_required(self):
        if self.status in {"confirmed", "excluded"} and not self.evidence_refs:
            raise ValueError("Confirmation and exclusion require real evidence")
        return self


class TargetBundle(Contract):
    snapshot_id: UUID
    candidates: BundleRef
    evidence: BundleRef
    decisions: BundleRef
