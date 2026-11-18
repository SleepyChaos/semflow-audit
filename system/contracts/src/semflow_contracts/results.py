"""Research results never imply a human confirmation, acceptance or publication."""

from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, Field, model_validator

from semflow_contracts.actions import ApprovalRequest
from semflow_contracts.baselines import StaticBaseline
from semflow_contracts.common import ArtifactRef, BundleRef, Contract, Digest, EntityRef
from semflow_contracts.discovery import CoverageReport
from semflow_contracts.errors import Failure
from semflow_contracts.repair import RepairResult, RepairVerifyResult, SuiteBuildResult
from semflow_contracts.rules import RuleResult
from semflow_contracts.runs import Implementation
from semflow_contracts.validation import ValidationReceipt

ExecutionStatus = Literal[
    "created",
    "running",
    "awaiting_input",
    "completed",
    "failed",
    "cancelled",
    "interrupted",
]


from pydantic import ConfigDict

from semflow_contracts.wire import schema_meaning


class Completeness(Contract):
    status: Literal["full", "partial", "none"]
    reasons: tuple[str, ...] = ()
    planned_units: int | None = Field(default=None, ge=0)
    completed_units: int | None = Field(default=None, ge=0)
    unassessed_refs: tuple[EntityRef, ...] = ()

    @model_validator(mode="after")
    def full_is_assessed(self):
        if self.status == "full" and self.unassessed_refs:
            raise ValueError("Unassessed entities cannot be full coverage")
        if (
            self.planned_units is not None
            and self.completed_units is not None
            and self.completed_units > self.planned_units
        ):
            raise ValueError("Completed units exceed the frozen plan")
        return self


class UsageEntry(Contract):
    provider: str
    model: str
    call_ids: tuple[UUID, ...]
    calls: int = Field(ge=0)
    input_tokens: int | None = Field(ge=0)
    output_tokens: int | None = Field(ge=0)
    completeness: Literal["complete", "partial", "unknown"]

    @model_validator(mode="after")
    def unique_calls(self):
        if len(set(self.call_ids)) != len(self.call_ids) or self.calls != len(
            self.call_ids
        ):
            raise ValueError("Provider usage must identify each call exactly once")
        return self


class Usage(Contract):
    calls: int = Field(ge=0)
    input_tokens: int | None = Field(ge=0)
    output_tokens: int | None = Field(ge=0)
    wall_seconds: float = Field(ge=0)
    tool_seconds: float | None = Field(default=None, ge=0)
    by_provider: tuple[UsageEntry, ...] = ()
    completeness: Literal["complete", "partial", "unknown"]

    @model_validator(mode="after")
    def complete_usage(self):
        identifiers = [
            identifier for entry in self.by_provider for identifier in entry.call_ids
        ]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("Usage cannot count a call twice")
        if self.completeness == "complete" and (
            self.calls != len(identifiers)
            or self.input_tokens is None
            or self.output_tokens is None
        ):
            raise ValueError(
                "Complete usage requires known tokens and identified calls"
            )
        return self


class Timestamps(Contract):
    created_at: AwareDatetime
    started_at: AwareDatetime | None = None
    ended_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def monotonic(self):
        if self.started_at and self.started_at < self.created_at:
            raise ValueError("Execution started before creation")
        if self.ended_at and self.ended_at < (self.started_at or self.created_at):
            raise ValueError("Execution ended before it started")
        return self


class BranchOutcome(Contract):
    branch: Literal["scan", "scout", "review"]
    execution_id: UUID
    status: ExecutionStatus
    result_manifest: ArtifactRef | None = None
    failure: Failure | None = None

    @model_validator(mode="after")
    def failed_has_reason(self):
        if self.status == "failed" and self.failure is None:
            raise ValueError("Failed branch requires a failure record")
        return self


class DiscoveryResult(Contract):
    baseline: StaticBaseline | None = None
    static_findings: BundleRef | None = None
    candidates: BundleRef
    evidence: BundleRef
    assessments: BundleRef | None = None
    coverage: CoverageReport
    branches: tuple[BranchOutcome, ...] = ()
    root_relations: ArtifactRef | None = None
    # Peer: discovery_outputs.export -> public.discovery.read_result -> platform projection.
    # AGENT: this versioned diagnostic trace preserves method-specific UI data;
    # scientific entities/statuses remain the typed bundles above, never inferred
    # from trace labels. Presentation ID/hash conversion belongs to the platform.
    analysis_trace: ArtifactRef | None = None
    project_map: ArtifactRef | None = None
    # Peer: CandidateReviewReport in review_handoff; optional for historical manifests.
    candidate_reviews: ArtifactRef | None = None


class ResultManifest(Contract):
    model_config = ConfigDict(json_schema_extra=schema_meaning("manifest"))

    schema_version: Literal["semflow.research.manifest/1.0"] = (
        "semflow.research.manifest/1.0"
    )
    execution_id: UUID
    revision: int = Field(ge=1)
    input_digest: Digest
    spec: ArtifactRef
    result: ArtifactRef
    artifacts: tuple[ArtifactRef, ...]
    final_event_seq: int = Field(ge=0)
    previous_manifest: ArtifactRef | None = None

    @model_validator(mode="after")
    def owned_inputs(self):
        if any(
            ref.owner_execution_id != self.execution_id
            for ref in (self.spec, self.result)
        ):
            raise ValueError("Manifest input and result must belong to its execution")
        return self


ModuleResult = (
    DiscoveryResult | RepairResult | SuiteBuildResult | RepairVerifyResult | RuleResult
)


class ResultEnvelope(Contract):
    model_config = ConfigDict(json_schema_extra=schema_meaning("result"))

    schema_version: Literal["semflow.research.result/1.0"] = (
        "semflow.research.result/1.0"
    )
    execution_id: UUID
    input_digest: Digest
    module: Literal["discovery", "repair", "rules"]
    operation: Literal[
        "scan",
        "scout",
        "review",
        "discover",
        "generate",
        "build_suite",
        "verify",
        "validate",
    ]
    implementation: Implementation
    execution_status: ExecutionStatus
    completeness: Completeness
    result: ModuleResult | None
    validation: tuple[ValidationReceipt, ...] = ()
    failure: Failure | None = None
    artifacts: tuple[ArtifactRef, ...] = ()
    usage: Usage
    timestamps: Timestamps
    # Interface peers: runtime.factory.assemble -> runtime.execution.execute.
    # AGENT: preserve the exact non-secret runtime resources separately from the
    # caller's profile name; never silently replace a profile on resume.
    resources_snapshot: ArtifactRef | None = None
    pending_action: ApprovalRequest | None = None
    # This field is omitted from the serialized result artifact to avoid a hash cycle.
    manifest: ArtifactRef | None = None

    @model_validator(mode="after")
    def independent_statuses(self):
        operations = {
            "discovery": {"scan", "scout", "review", "discover"},
            "repair": {"generate", "build_suite", "verify"},
            "rules": {"generate", "validate"},
        }
        if self.operation not in operations[self.module]:
            raise ValueError("Operation does not belong to the result module")
        expected = {
            "discovery": DiscoveryResult,
            "rules": RuleResult,
            "repair": {
                "generate": RepairResult,
                "build_suite": SuiteBuildResult,
                "verify": RepairVerifyResult,
            }.get(self.operation),
        }[self.module]
        if self.result is not None and not isinstance(self.result, expected):
            raise ValueError("Result payload does not match module and operation")
        if self.execution_status == "failed" and self.failure is None:
            raise ValueError("Failed execution requires a failure record")
        if self.execution_status == "completed" and (
            self.failure or self.result is None
        ):
            raise ValueError(
                "Completed execution requires a result without execution failure"
            )
        if (self.execution_status == "awaiting_input") != (
            self.pending_action is not None
        ):
            raise ValueError("Waiting execution requires exactly one pending action")
        if (
            self.pending_action
            and self.pending_action.execution_id != self.execution_id
        ):
            raise ValueError("Approval action belongs to a different execution")
        return self
