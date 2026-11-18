"""Diagnostic continuation plan carried by the discovery trace."""

from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from semflow_contracts.common import (
    Contract,
    Digest,
    EntityRef,
    RelativePath,
    SourceLocation,
)
from semflow_contracts.discovery import AssessmentRecord


class ReviewSourceWindow(Contract):
    file: RelativePath
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)

    @model_validator(mode="after")
    def ordered(self):
        if self.end_line < self.start_line:
            raise ValueError("Source window ends before it starts")
        return self


class ReviewNextAction(Contract):
    # Peers: research.review_next_action produces and runtime.review_continuation
    # consumes these actions. The platform projects them to ReviewHandoff.
    kind: Literal[
        "gather_source", "retry_execution", "collect_material", "manual_triage", "none"
    ]
    source_windows: tuple[ReviewSourceWindow, ...] = Field(default=(), max_length=3)

    @model_validator(mode="after")
    def actionable_source(self):
        if bool(self.source_windows) != (self.kind == "gather_source"):
            raise ValueError("Only source gathering has bounded windows")
        if any(w.end_line - w.start_line >= 151 for w in self.source_windows):
            raise ValueError("Continuation source window exceeds the read tool limit")
        return self


class ReviewPremise(Contract):
    role: str = Field(min_length=1)
    status: Literal["established", "contradicted", "missing", "not_applicable"]
    explanation: str = Field(min_length=1)
    policy_basis: str | None = None
    # Source-grounded means quote and citations passed the existing source gate.
    # It is not a proof of data flow, path feasibility or runtime behavior.
    verification: Literal["source_grounded", "model_inference", "unresolved"]
    quote: str = ""
    evidence_refs: tuple[EntityRef, ...] = ()

    @model_validator(mode="after")
    def grounding(self):
        if self.verification == "source_grounded" and (
            not self.quote
            or not self.evidence_refs
            or self.status not in {"established", "contradicted"}
        ):
            raise ValueError("Source-grounded premises require a quote and citations")
        if self.status == "missing" and self.verification != "unresolved":
            raise ValueError("A missing premise cannot be verified")
        return self


class CandidateReviewAttempt(Contract):
    candidate_ref: EntityRef
    previous_candidate_ref: EntityRef | None = None
    source_type: Literal["static", "scout"]
    location: SourceLocation
    weakness: str = Field(min_length=1)
    # Execution lifecycle, model conclusion (assessment), and evidence outcome
    # are independent. Missing assessment never implies a negative verdict.
    execution_state: Literal[
        "not_scheduled", "not_run", "completed", "partial", "failed", "interrupted"
    ]
    evidence_state: Literal[
        "not_assessed", "validated_references", "unresolved", "validation_failed"
    ]
    assessment: AssessmentRecord | None = None
    stop_code: str | None = None
    stop_detail: str | None = None
    premises: tuple[ReviewPremise, ...] = ()
    runtime_unknowns: tuple[str, ...] = ()
    validation_errors: tuple[str, ...] = ()
    batch_ids: tuple[str, ...] = ()
    observed_source_windows: tuple[ReviewSourceWindow, ...] = ()
    next_action: ReviewNextAction | None = None

    @model_validator(mode="after")
    def assessment_identity(self):
        if self.assessment and self.assessment.candidate_ref != self.candidate_ref:
            raise ValueError("Assessment identifies another candidate")
        if self.execution_state == "completed" and self.assessment is None:
            raise ValueError("A completed candidate needs an accepted assessment")
        if self.assessment and self.execution_state not in {"completed", "partial"}:
            raise ValueError(
                "An accepted assessment needs completed or partial execution"
            )
        return self


class CandidateReviewReport(Contract):
    # WIRE: discovery_outputs -> public.discovery_results -> platform projection.
    # Draft and historic results can omit this versioned companion artifact.
    schema_version: Literal["semflow.candidate-review-report/1"] = (
        "semflow.candidate-review-report/1"
    )
    execution_id: UUID
    snapshot_id: UUID
    source_digest: Digest
    records: tuple[CandidateReviewAttempt, ...]

    @model_validator(mode="after")
    def unique_targets(self):
        ids = {row.candidate_ref.entity_id for row in self.records}
        if len(ids) != len(self.records) or any(
            row.candidate_ref.execution_id != self.execution_id
            or row.location.snapshot_id != self.snapshot_id
            for row in self.records
        ):
            raise ValueError("Candidate review report has duplicate or foreign records")
        return self
