"""Evidence-backed reviews and non-destructive root-cause relation proposals."""

from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from app.contracts.review import CandidateAssessment, ReviewResponseV2
from app.contracts.stages import StrictModel


class CheckedAssessment(CandidateAssessment):
    checked_premises: list[str] = Field(default_factory=list, max_length=12)
    missing_premises: list[str] = Field(default_factory=list, max_length=12)
    counterevidence_ids: list[UUID] = Field(default_factory=list, max_length=20)
    runtime_unknowns: list[str] = Field(default_factory=list, max_length=12)

    @model_validator(mode="after")
    def justified_verdict(self):
        if self.assessment in {"supported", "excluded"} and self.missing_premises:
            raise ValueError(
                "Unresolved necessary premises require an uncertain verdict"
            )
        if self.assessment == "excluded" and not self.counterevidence_ids:
            raise ValueError("Exclusion requires explicit counterevidence")
        if self.assessment in {"supported", "excluded"} and not self.checked_premises:
            raise ValueError("Verdict requires checked premises")
        return self


class RootRelation(StrictModel):
    candidate_ids: list[UUID] = Field(min_length=2, max_length=8)
    relationship: Literal["same_root_cause", "related", "distinct"]
    reason: str = Field(min_length=10, max_length=2000)
    evidence_ids: list[UUID] = Field(min_length=1, max_length=30)


class UnifiedReviewResponse(ReviewResponseV2):
    candidate_assessments: list[CheckedAssessment] = Field(
        default_factory=list, max_length=50
    )
    root_relations: list[RootRelation] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def relation_action(self):
        if self.action == "tool" and self.root_relations:
            raise ValueError("Tool request cannot assert root relations")
        return self


class FinalUnifiedReviewResponse(UnifiedReviewResponse):
    action: Literal["final"] = "final"
    tool: None = None
