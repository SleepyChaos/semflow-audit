"""Repair and before/after validation contracts, without platform acceptance."""

from typing import Literal
from uuid import UUID

from pydantic import ConfigDict, Field, model_validator

from semflow_contracts.baselines import StaticBaseline
from semflow_contracts.common import (
    ArtifactRef,
    BundleRef,
    Contract,
    Digest,
    EntityRef,
    RelativePath,
    SourceSnapshot,
)
from semflow_contracts.discovery import ScanInput
from semflow_contracts.evidence import TargetBundle
from semflow_contracts.validation import ValidationReceipt
from semflow_contracts.wire import schema_meaning


class SuiteRef(Contract):
    suite_id: UUID
    definition: ArtifactRef
    suite_hash: Digest
    target_refs: tuple[EntityRef, ...] = Field(min_length=1)
    source: Literal["human", "model_generated", "external_fixture"]
    image_digest: str = Field(min_length=1)


class PatchScope(Contract):
    writable_paths: tuple[RelativePath, ...] = Field(min_length=1, max_length=30)
    # Interface peer: evidence.EvidenceService.allowed enforces this exact scope.
    # AGENT: changing empty/scope semantics requires changing that receiver too.
    readable_paths: tuple[RelativePath, ...] = Field(
        description="Read-only scope; an empty list limits reading to writable_paths. Writable files are always readable, never implicitly expandable by the model.",
    )
    max_changed_files: int = Field(ge=1, le=30)
    enforce_observed_ranges: Literal[True] = True


class TestPlan(Contract):
    runner: Literal["python_pytest", "javascript_test"]
    suite: SuiteRef | None = None
    resource_profile: str = Field(min_length=1)


class RepairValidationPlan(Contract):
    # Interface peers: repair_operations.validate_controls / RepairService.validate.
    # AGENT: syntax and project_tests are independent requested checks; update
    # both the dispatcher and receipt projection when changing omission semantics.
    syntax: bool
    project_tests: TestPlan | None = None
    rescan: ScanInput | None = None
    # Peers: repair_rescan.receive / research_bridge.repair_baseline.freeze.
    # AGENT: this is the original actual DB/SARIF/source identity, not a request
    # to scan again with current defaults. Update sender and receiver together.
    static_baseline: StaticBaseline | None = None
    before_after: bool

    @model_validator(mode="after")
    def rescan_requires_baseline(self):
        if self.rescan is not None and self.static_baseline is None:
            raise ValueError("Rescan requires an immutable original static baseline")
        return self


class InspectionLimits(Contract):
    max_steps: int = Field(ge=1)
    # Peer: runtime.factory.policy_for -> repair_source_tools.remaining.
    # AGENT: initial reads reserve part of the total; never widen them to max_steps
    # when a producer supplies this value. None preserves older request semantics.
    initial_source_steps: int | None = Field(default=None, ge=1)
    max_context_chars: int = Field(ge=1)
    max_expanded_context_chars: int = Field(ge=1)

    @model_validator(mode="after")
    def initial_within_total(self):
        if (
            self.initial_source_steps is not None
            and self.initial_source_steps > self.max_steps
        ):
            raise ValueError(
                "Initial source reads cannot exceed the total source budget"
            )
        return self


class FeedbackPolicy(Contract):
    # Interface peers: repair_candidate_validation and graphs.repair.feedback.
    # AGENT: disabled consistency must not call the model or become a passed check;
    # stopping/refresh controls must be executed or explicitly rejected by the method.
    version: str = Field(min_length=1)
    semantic_consistency: bool
    refresh_understanding: bool
    stop_on_environment_error: bool


class RepairMethodPolicy(Contract):
    version: str = Field(min_length=1)
    max_candidates: int = Field(ge=1)
    # Peer: runtime.factory.policy_for -> adapters.ai.policy.CallBudget.reserve.
    # AGENT: this independent method call cap also applies in progress mode;
    # it is neither the target count nor the global execution call budget.
    model_call_limit: int | None = Field(default=None, ge=1)
    inspection_limits: InspectionLimits
    feedback_policy: FeedbackPolicy
    selected_suite_feedback: bool
    baseline_reuse: bool


# WIRE-SEND:research.openhands — peer: runtime.repair_operations / platform bridge.
# AGENT: this declaration freezes the worker identity and resource semantics;
# update the receiver and compatibility tests with any field meaning change.
class OpenHandsPolicy(Contract):
    """Frozen OpenHands worker identity and resource limits."""

    model_config = ConfigDict(json_schema_extra=schema_meaning("openhands"))

    # Peers: platform repair_requests -> runtime.factory.policy_for -> adapters.repair.openhands.generate.
    # AGENT: SDK/image/prompt/model/scope/budgets are one semantic contract;
    # changing a producer field requires checking worker receipt and receiver.
    sdk_version: Literal["1.56.0"] = "1.56.0"
    image_digest: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    model: str = Field(min_length=1)
    endpoint_profile: str = Field(min_length=1)
    prompt_version: int = Field(ge=1)
    max_steps: int = Field(ge=1, le=1000)
    timeout_seconds: int = Field(ge=1, le=7200)
    stall_timeout_seconds: int = Field(default=240, ge=1, le=7200)
    output_tokens: int = Field(ge=1)
    thinking_mode: str | None = None
    dependency_environment: str | None = None
    dependency_tools: str | None = None
    development_command: str | None = None


class RepairGenerateInput(Contract):
    engine: Literal["native", "openhands"]
    targets: TargetBundle
    patch_scope: PatchScope
    validation_plan: RepairValidationPlan
    suite: SuiteRef | None = None
    openhands: OpenHandsPolicy | None = None
    method_policy: RepairMethodPolicy

    @model_validator(mode="after")
    def suite_required(self):
        if self.engine == "openhands" and self.openhands is None:
            raise ValueError("OpenHands engine requires a frozen OpenHands policy")
        if (
            self.validation_plan.before_after
            or self.method_policy.selected_suite_feedback
        ) and self.suite is None:
            raise ValueError("Selected assertions and before/after checks need a suite")
        return self


class SuiteBuildInput(Contract):
    targets: TargetBundle
    # Peers: suite_requests.freeze_build -> suite_build.build.
    # AGENT: body is raw UTF-8 text (text/plain, semflow.requested-behavior/1),
    # not a JSON string or model output. Preserve requirements without truncation.
    requested_behavior: ArtifactRef
    runtime_profile: str = Field(min_length=1)


class RepairVerifyInput(Contract):
    repair: EntityRef
    patch: ArtifactRef
    patched_source: SourceSnapshot
    suite: SuiteRef
    validation_plan: RepairValidationPlan


class RepairResult(Contract):
    repair_id: UUID
    target_refs: tuple[EntityRef, ...] = Field(min_length=1)
    attempts: ArtifactRef
    selected_attempt_id: UUID | None = None
    patch: ArtifactRef | None = None
    patched_source: SourceSnapshot | None = None
    checks: tuple[ValidationReceipt, ...] = ()
    outcome: Literal["checks_passed", "needs_review", "no_patch"]
    semantic_context: ArtifactRef
    original_snapshot_unchanged: Literal[True]

    @model_validator(mode="after")
    def delivered_patch(self):
        if self.outcome == "checks_passed" and (
            self.patch is None
            or self.patched_source is None
            or not self.checks
            or any(check.status != "passed" for check in self.checks)
        ):
            raise ValueError(
                "Passed repair requires a patch and executed passing checks"
            )
        return self


class AttemptRecord(Contract):
    # Interface peers: runtime.repair_outputs.export / read_attempts.
    # AGENT: these digests identify referenced bytes; native graph checkpoint
    # hashes use their own format and cannot be substituted despite equal length.
    attempt_id: UUID
    ordinal: int = Field(ge=1)
    context_digest: Digest
    context: ArtifactRef
    proposal: ArtifactRef
    patch: ArtifactRef | None = None
    patched_tree_sha256: Digest | None = None
    patched_source: SourceSnapshot | None = None
    checks: tuple[ValidationReceipt, ...] = ()
    diagnosis: ArtifactRef | None = None
    # Peer: repair_openhands.finalize / repair_outputs.export / platform projection.
    # AGENT: engine receipt preserves worker status/usage separately from patch
    # checks; absence is not a successful zero-usage result.
    # Peer: runtime.repair_outputs.export / read_attempts and OpenHandsReceipt.
    # AGENT: new output retains all worker files even if independent checks fail;
    # older usage-only refs stay readable and never imply complete engine evidence.
    engine_receipt: ArtifactRef | None = None
    selected: bool


class SuiteBuildResult(Contract):
    suite: SuiteRef
    review_required: Literal[True] = True
    generation_evidence: BundleRef


class ComparisonIdentity(Contract):
    before_tree_sha256: Digest
    patch_sha256: Digest
    after_tree_sha256: Digest
    suite_hash: Digest
    image_digest: str = Field(min_length=1)
    target_digest: Digest


class RepairVerifyResult(Contract):
    repair_ref: EntityRef
    identity: ComparisonIdentity
    receipt: ValidationReceipt


class RepairAttempts(Contract):
    """A versioned attempt history; passing checks do not accept a patch."""

    # Interface peers: runtime.repair_outputs.export -> read_attempts / ledger.inspect.
    # AGENT: preserve ordinal/history and exact proposal/patch/context identities
    # at both ends; a selected candidate is not a platform acceptance decision.
    model_config = ConfigDict(json_schema_extra=schema_meaning("repair_attempts"))
    schema_version: Literal["semflow.repair-attempts/1"] = "semflow.repair-attempts/1"
    execution_id: UUID
    snapshot_id: UUID
    records: tuple[AttemptRecord, ...]

    @model_validator(mode="after")
    def ordered_attempts(self):
        ordinals = [record.ordinal for record in self.records]
        if ordinals != sorted(set(ordinals)) or len(
            {record.attempt_id for record in self.records}
        ) != len(self.records):
            raise ValueError(
                "Repair attempts require unique IDs and increasing ordinals"
            )
        if sum(record.selected for record in self.records) > 1:
            raise ValueError("Only one repair candidate can be selected")
        for record in self.records:
            if (
                record.patched_source is not None
                and record.patched_source.tree_sha256 != record.patched_tree_sha256
            ):
                raise ValueError(
                    "Repair attempt patched source identity does not match its frozen tree"
                )
            if (
                record.context.sha256 != record.context_digest
                or record.context.owner_execution_id != self.execution_id
            ):
                raise ValueError(
                    "Repair attempt context reference does not match its frozen bytes"
                )
            if record.proposal.owner_execution_id != self.execution_id or (
                record.patch and record.patch.owner_execution_id != self.execution_id
            ):
                raise ValueError("Repair attempt artifacts belong to another execution")
        return self
