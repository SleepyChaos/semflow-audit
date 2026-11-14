"""Versioned experiment plans; evaluation labels are not execution inputs."""

from pathlib import Path
from typing import Literal, Self
from uuid import UUID

from pydantic import Field, model_validator

from app.contracts.stages import StrictModel


class StageBudget(StrictModel):
    max_calls: int = Field(default=24, ge=1)
    max_tokens: int = Field(default=100000, ge=1)
    max_seconds: int = Field(default=300, ge=1)
    model: str | None = Field(default=None, min_length=1, max_length=200)


class RuleExperiment(StrictModel):
    retrieval_mode: Literal["auto", "bm25", "vector", "hybrid"] | None = None
    collection_routing: bool | None = None
    corpus_document_ids: list[UUID] | None = Field(default=None, min_length=1)
    full_feedback: bool | None = None
    generation_constraint: bool | None = None
    progress_feedback: bool | None = None
    compact_context: bool | None = None
    source_preparation_context: bool | None = None
    rag_before_inspection: bool | None = None


class ExperimentStage(StrictModel):
    kind: Literal[
        "scout",
        "review",
        "repair",
        "rule",
        "report",
        "verification_suite",
        "verification",
    ]
    prompt_version: str | None = Field(default=None, pattern=r"^[1-9][0-9]*$")
    inputs: dict = Field(default_factory=dict)
    budget: StageBudget = Field(default_factory=StageBudget)
    rule_experiment: RuleExperiment | None = None

    @model_validator(mode="after")
    def input_contract(self) -> Self:
        from app.contracts.stage_execution import validate_inputs

        # The application validates again when it has the real audit/target IDs.
        self.inputs = validate_inputs(self.kind, self.inputs)
        if self.rule_experiment is not None and self.kind != "rule":
            raise ValueError("rule_experiment only applies to rule generation")
        if self.kind == "scout" and self.inputs.get("continuation_from_id"):
            raise ValueError("Use the dedicated scout continuation workflow")
        if self.kind == "report" and self.inputs:
            raise ValueError("Report inputs are derived from the audit")
        if self.kind == "verification":
            if set(self.inputs) != {"repair_id", "suite_id"}:
                raise ValueError("Verification requires only repair_id and suite_id")
            self.inputs = {key: str(UUID(value)) for key, value in self.inputs.items()}
        return self


class ExperimentSample(StrictModel):
    id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
    archive: Path | None = None
    audit_id: UUID | None = None
    language: Literal["python", "javascript"] = "python"
    # Static-only is the explicit baseline; dual scan opts into additional model calls.
    dual_engine: bool = False
    stages: list[ExperimentStage] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def source_contract(self) -> Self:
        if (self.archive is None) == (self.audit_id is None):
            raise ValueError("Specify exactly one of archive and audit_id")
        if self.audit_id and self.dual_engine:
            raise ValueError("dual_engine only applies to a new archive scan")
        if self.audit_id and not self.stages:
            raise ValueError("An existing audit needs at least one requested stage")
        return self


class ExperimentPlan(StrictModel):
    schema_version: Literal[1] = 1
    name: str = Field(min_length=1, max_length=120)
    repetitions: int = Field(default=1, ge=1, le=100)
    samples: list[ExperimentSample] = Field(min_length=1, max_length=10000)

    @model_validator(mode="after")
    def unique_samples(self) -> Self:
        ids = [sample.id for sample in self.samples]
        if len(set(ids)) != len(ids):
            raise ValueError("Sample IDs must be unique")
        return self
