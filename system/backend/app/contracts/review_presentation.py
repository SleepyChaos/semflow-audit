"""Project-specific review narratives, source citations and unexecuted examples."""

from typing import Literal
from uuid import UUID

from pydantic import Field

from app.contracts.discovery_semantics import (
    SemanticAssessment,
    UnifiedReviewResponseV8,
)
from app.contracts.stages import StrictModel


class ExploitationExample(StrictModel):
    status: Literal["illustrative", "blocked", "missing_preconditions"]
    entrypoint: str = Field(default="", max_length=300)
    prerequisites: list[str] = Field(default_factory=list, max_length=6)
    steps: list[str] = Field(default_factory=list, max_length=6)
    example: str = Field(default="", max_length=2000)
    expected_result: str = Field(min_length=10, max_length=1000)
    source_quote: str = Field(default="", max_length=300)
    evidence_ids: list[UUID] = Field(default_factory=list, max_length=12)
    execution_status: Literal["not_executed"] = "not_executed"


class ReviewDetail(StrictModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=10, max_length=1500)
    impact: str = Field(min_length=10, max_length=1000)
    exploitation: ExploitationExample
    evidence_ids: list[UUID] = Field(default_factory=list, max_length=20)


class PresentedAssessment(SemanticAssessment):
    detail: ReviewDetail


class PresentedReviewResponse(UnifiedReviewResponseV8):
    candidate_assessments: list[PresentedAssessment] = Field(
        default_factory=list, max_length=50
    )


class FinalPresentedReviewResponse(PresentedReviewResponse):
    action: Literal["final"] = "final"
    tool: None = None
