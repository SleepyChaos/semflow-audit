"""V2: assessments do not manufacture vulnerability candidates."""

from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from app.contracts.stages import StrictModel, ToolCall


class AnchorAssessment(StrictModel):
    anchor_id: str
    weakness: str = Field(default="unknown", pattern=r"^(unknown|CWE-[0-9]+)$")
    assessment: Literal["reviewed", "excluded", "insufficient"]
    reason: str = Field(min_length=10, max_length=5000)
    evidence_ids: list[UUID] = Field(default_factory=list, max_length=30)


class CandidateAssessment(StrictModel):
    candidate_id: UUID
    weakness: str = Field(default="unknown", pattern=r"^(unknown|CWE-[0-9]+)$")
    assessment: Literal["supported", "excluded", "pending", "insufficient"]
    reason: str = Field(min_length=10, max_length=5000)
    evidence_ids: list[UUID] = Field(default_factory=list, max_length=30)


class PrimaryLocation(StrictModel):
    file: str = Field(min_length=1, max_length=500)
    line: int = Field(ge=1, strict=True)


class NewFinding(StrictModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=10, max_length=5000)
    weakness: str = Field(default="unknown", pattern=r"^(unknown|CWE-[0-9]+)$")
    primary_location: PrimaryLocation
    related_target: str
    evidence_ids: list[UUID] = Field(min_length=1, max_length=30)


class ReviewResponseV2(StrictModel):
    action: Literal["tool", "final"]
    tool: ToolCall | None = None
    anchor_assessments: list[AnchorAssessment] = Field(
        default_factory=list, max_length=100
    )
    candidate_assessments: list[CandidateAssessment] = Field(
        default_factory=list, max_length=50
    )
    new_findings: list[NewFinding] = Field(default_factory=list, max_length=50)
    summary: str = Field(default="", max_length=5000)

    @model_validator(mode="after")
    def mutually_exclusive(self):
        if self.action == "tool" and (
            self.tool is None
            or self.anchor_assessments
            or self.candidate_assessments
            or self.new_findings
        ):
            raise ValueError("Tool responses must contain only one tool request")
        if self.action == "final" and self.tool is not None:
            raise ValueError("Final response cannot request an unexecuted tool")
        return self
