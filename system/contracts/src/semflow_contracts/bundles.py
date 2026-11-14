"""Typed JSON bundles crossing kernel/CLI/platform boundaries.

Interface peers: research.runtime.bundle_io and runtime.discovery_outputs.
AGENT: retain producer/snapshot identity and entity membership at both ends;
changing a JSON record's meaning requires updating its codec and compatibility
fixtures, not merely renaming a key at the producer.
"""

from typing import Generic, Literal, TypeVar
from uuid import UUID

from pydantic import ConfigDict, Field, model_validator

from semflow_contracts.common import ArtifactRef, BundleRef, Contract, SourceLocation
from semflow_contracts.discovery import AssessmentRecord, CandidateRecord
from semflow_contracts.evidence import DecisionRecord, EvidenceRecord
from semflow_contracts.wire import schema_meaning

Record = TypeVar("Record", bound=Contract)


class Bundle(Contract, Generic[Record]):
    model_config = ConfigDict(json_schema_extra=schema_meaning("bundle"))
    schema_version: Literal["semflow.research.bundle/1"] = "semflow.research.bundle/1"
    execution_id: UUID
    snapshot_id: UUID
    records: tuple[Record, ...]

    @model_validator(mode="after")
    def owned_records(self):
        identifiers = []
        for record in self.records:
            fields = (
                "candidate_id",
                "evidence_id",
                "assessment_id",
                "decision_id",
                "finding_id",
            )
            identifier = next(
                getattr(record, key) for key in fields if hasattr(record, key)
            )
            identifiers.append(identifier)
            if getattr(record, "execution_id", self.execution_id) != self.execution_id:
                raise ValueError(
                    "Bundle contains a record produced by another execution"
                )
            if getattr(record, "snapshot_id", self.snapshot_id) != self.snapshot_id:
                raise ValueError(
                    "Bundle contains a record from another source snapshot"
                )
            points = list(getattr(record, "locations", ()))
            points.extend(
                point for flow in getattr(record, "code_flows", ()) for point in flow
            )
            if getattr(record, "primary_location", None) is not None:
                points.append(record.primary_location)
            if any(point.snapshot_id != self.snapshot_id for point in points):
                raise ValueError(
                    "Bundle contains a location from another source snapshot"
                )
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("Bundle entity IDs must be unique")
        return self


class StaticFindingRecord(Contract):
    finding_id: UUID
    execution_id: UUID
    raw_id: str = Field(min_length=1)
    # Peers: discovery_outputs.export_static / bundle_io.import_targets / Web input codec.
    # AGENT: preserve supplemental rule provenance through review; this does not
    # grant platform publication or ownership rights to the receiver.
    rule_version: str | None = None
    origin: Literal["baseline", "custom_rule"] = "baseline"
    rule: str = Field(min_length=1)
    message: str
    locations: tuple[SourceLocation, ...] = Field(min_length=1)
    code_flows: tuple[tuple[SourceLocation, ...], ...] = ()
    tags: tuple[str, ...] = ()
    level: str
    security_severity: str | None = None
    sarif: ArtifactRef


CandidateBundle = Bundle[CandidateRecord]
EvidenceBundle = Bundle[EvidenceRecord]
DecisionBundle = Bundle[DecisionRecord]
AssessmentBundle = Bundle[AssessmentRecord]
StaticFindingBundle = Bundle[StaticFindingRecord]


class BundleIndex(Contract):
    # Interface peers: runtime.discovery_merge.index -> bundle_reader.resolve_bundle.
    # AGENT: the coordinator owns this index, while every member retains its own
    # producer, record IDs and artifact bytes. Never relabel members as parent output.
    model_config = ConfigDict(json_schema_extra=schema_meaning("bundle_index"))
    schema_version: Literal["semflow.research.bundle-index/1"] = (
        "semflow.research.bundle-index/1"
    )
    execution_id: UUID
    snapshot_id: UUID
    entity_type: Literal[
        "candidate", "evidence", "assessment", "static_finding", "decision"
    ]
    members: tuple[BundleRef, ...]

    @model_validator(mode="after")
    def unique_members(self):
        identities = [ref.model_dump_json() for ref in self.members]
        if len(set(identities)) != len(identities):
            raise ValueError("Bundle index cannot repeat a member")
        return self
