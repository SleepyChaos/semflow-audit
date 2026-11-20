"""Versioned module/operation-discriminated execution inputs."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import ConfigDict, Field, TypeAdapter, model_validator

from semflow_contracts.common import (
    ArtifactRef,
    Contract,
    Digest,
    Language,
    SourceSnapshot,
)
from semflow_contracts.discovery import (
    DiscoverInput,
    ReviewInput,
    ScanInput,
    ScoutInput,
)
from semflow_contracts.evidence import TargetBundle
from semflow_contracts.repair import (
    RepairGenerateInput,
    RepairVerifyInput,
    SuiteBuildInput,
)
from semflow_contracts.rules import RuleGenerateInput, RuleValidateInput
from semflow_contracts.wire import schema_meaning


class Lineage(Contract):
    experiment_id: UUID | None = None
    sample_id: str | None = None
    repetition: int | None = Field(default=None, ge=1)
    epoch: str | None = None
    parent_execution_id: UUID | None = None
    retry_of: UUID | None = None
    upstream: tuple[ArtifactRef, ...] = ()


class Implementation(Contract):
    method_id: str = Field(min_length=1)
    method_version: str = Field(min_length=1)
    code_digest: Digest
    dependency_lock_digest: Digest


class PromptSnapshot(Contract):
    role: str = Field(min_length=1)
    template_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    content: ArtifactRef
    sha256: Digest

    @model_validator(mode="after")
    def content_digest(self):
        if self.sha256 != self.content.sha256:
            raise ValueError("Prompt digest does not match frozen content")
        return self


class ModelProfile(Contract):
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    revision: str | None = None
    endpoint_profile: str = Field(pattern=r"^[A-Za-z0-9._-]+$")
    temperature: float | None = None
    thinking_mode: str | None = None
    output_schema_version: str = Field(min_length=1)
    # Peer: CompatibleModel.generate. Freeze endpoint capability per run;
    # absence keeps the historical JSON-object request format.
    scout_response_format: Literal["json_object", "json_schema"] | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    output_tokens: int = Field(
        default=6000,
        ge=1,
        description="Per-call output limit, separate from ExecutionPolicy.max_tokens (total budget). Producers freeze this default; receivers must not infer it from the total budget.",
    )


class ExecutionPolicy(Contract):
    mode: Literal["bounded", "progress"]
    max_calls: int | None = Field(ge=1)
    max_tokens: int | None = Field(ge=1)
    max_seconds: int | None = Field(ge=1)
    per_call_timeout_seconds: int = Field(ge=1)
    tool_timeout_seconds: int = Field(ge=1)
    # Peers: factory.assemble / platform repair_requests. AGENT: scanning and
    # container test timeouts are independent; None retains older profiles.
    scan_timeout_seconds: int | None = Field(default=None, ge=1)
    max_attempts: int = Field(ge=1)
    max_no_progress: int = Field(default=3, ge=1)
    max_context_chars: int = Field(ge=1)
    resource_profile: str = Field(min_length=1)
    decision_policy: Literal["human_only", "experiment_declared"]

    @model_validator(mode="after")
    def bounded_has_limits(self):
        if self.mode == "bounded" and any(
            value is None
            for value in (self.max_calls, self.max_tokens, self.max_seconds)
        ):
            raise ValueError("Bounded execution requires all three total limits")
        return self


class RunBase(Contract):
    model_config = ConfigDict(json_schema_extra=schema_meaning("run"))

    schema_version: Literal["semflow.research.run/1.0"] = "semflow.research.run/1.0"
    execution_id: UUID
    lineage: Lineage
    source: SourceSnapshot
    language: Language
    implementation: Implementation
    prompts: tuple[PromptSnapshot, ...]
    model: ModelProfile | None
    policy: ExecutionPolicy

    @model_validator(mode="after")
    def input_identities(self):
        if self.language not in self.source.languages:
            raise ValueError("Analysis language is outside the source snapshot")
        if len({prompt.role for prompt in self.prompts}) != len(self.prompts):
            raise ValueError("Duplicate prompt role")
        if self.execution_id in {
            self.lineage.retry_of,
            self.lineage.parent_execution_id,
        }:
            raise ValueError("An execution cannot be its own parent or retry")
        inputs = self.inputs
        target = getattr(inputs, "targets", None) or getattr(inputs, "target", None)
        if (
            isinstance(target, TargetBundle)
            and target.snapshot_id != self.source.snapshot_id
        ):
            raise ValueError("Target bundle belongs to a different source snapshot")
        needs_model = self.operation in {"scout", "review", "generate", "build_suite"}
        if isinstance(inputs, DiscoverInput):
            needs_model = inputs.scout is not None or inputs.review is not None
        if needs_model and (not self.prompts or self.model is None):
            raise ValueError(
                "Model operations require explicit frozen prompts and model"
            )
        if (
            isinstance(inputs, RuleValidateInput)
            and inputs.query.language != self.language
        ):
            raise ValueError("Rule language does not match the requested source")
        scans = [inputs] if isinstance(inputs, ScanInput) else []
        if isinstance(inputs, DiscoverInput) and inputs.scan:
            scans.append(inputs.scan)
        for scan in scans:
            if any(rule.language != self.language for rule in scan.supplemental_rules):
                raise ValueError("Supplemental rule language does not match the source")
        return self


class ScanSpec(RunBase):
    module: Literal["discovery"]
    operation: Literal["scan"]
    inputs: ScanInput


class ScoutSpec(RunBase):
    module: Literal["discovery"]
    operation: Literal["scout"]
    inputs: ScoutInput


class ReviewSpec(RunBase):
    module: Literal["discovery"]
    operation: Literal["review"]
    inputs: ReviewInput


class DiscoverSpec(RunBase):
    module: Literal["discovery"]
    operation: Literal["discover"]
    inputs: DiscoverInput


class RepairGenerateSpec(RunBase):
    module: Literal["repair"]
    operation: Literal["generate"]
    inputs: RepairGenerateInput


class SuiteBuildSpec(RunBase):
    module: Literal["repair"]
    operation: Literal["build_suite"]
    inputs: SuiteBuildInput


class RepairVerifySpec(RunBase):
    module: Literal["repair"]
    operation: Literal["verify"]
    inputs: RepairVerifyInput

    # Peer: repair_verify.verify / platform comparison_requests.freeze_verify.
    # AGENT: the JSON schema must also forbid unused model/Prompt controls;
    # independent assertions execute tools and never become model opinions.
    model: None = None
    prompts: tuple[PromptSnapshot, ...] = Field(default=(), max_length=0)


class RuleGenerateSpec(RunBase):
    module: Literal["rules"]
    operation: Literal["generate"]
    inputs: RuleGenerateInput


class RuleValidateSpec(RunBase):
    module: Literal["rules"]
    operation: Literal["validate"]
    inputs: RuleValidateInput


DiscoverySpec = Annotated[
    ScanSpec | ScoutSpec | ReviewSpec | DiscoverSpec, Field(discriminator="operation")
]
RepairSpec = Annotated[
    RepairGenerateSpec | SuiteBuildSpec | RepairVerifySpec,
    Field(discriminator="operation"),
]
RuleSpec = Annotated[
    RuleGenerateSpec | RuleValidateSpec, Field(discriminator="operation")
]
RunSpec = Annotated[
    DiscoverySpec | RepairSpec | RuleSpec, Field(discriminator="module")
]
RUN_ADAPTER = TypeAdapter(RunSpec)


def validate_spec(value: dict | RunBase) -> RunSpec:
    # WIRE-RECV:research.run — peer: semflow_cli.main.dispatch / platform request mapping.
    # execution_id is a research ID; never reinterpret platform stage IDs or defaults.
    # AGENT: update wire.py, both producers and compatibility tests when changing semantics.
    # Revalidation also catches models constructed/copied without validators.
    if isinstance(value, RunBase):
        value = value.model_dump(mode="json")
    return RUN_ADAPTER.validate_python(value)
