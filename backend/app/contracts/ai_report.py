"""Narrative only: a report cannot mutate findings, checks or human decisions."""

import re

from pydantic import Field, model_validator

from app.contracts.stages import StrictModel


def require_chinese(texts):
    if any(not re.search(r"[\u4e00-\u9fff]", text) for text in texts):
        raise ValueError(
            "Reader-facing explanations and suggestions must be in Chinese"
        )


class ReportIssue(StrictModel):
    candidate_id: str
    title: str = Field(min_length=2, max_length=120)
    explanation: str = Field(min_length=10, max_length=1800)
    impact: str = Field(min_length=10, max_length=1200)
    fix_suggestions: list[str] = Field(min_length=1, max_length=6)
    verification_suggestions: list[str] = Field(min_length=1, max_length=6)
    evidence_ids: list[str] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def chinese(self):
        require_chinese(
            [
                self.title,
                self.explanation,
                self.impact,
                *self.fix_suggestions,
                *self.verification_suggestions,
            ]
        )
        return self


class AIReportResponse(StrictModel):
    overview: str = Field(min_length=10, max_length=2500)
    issues: list[ReportIssue] = Field(default_factory=list, max_length=30)
    repair_review: str = Field(min_length=10, max_length=2500)
    limitations: list[str] = Field(min_length=1, max_length=12)
    next_steps: list[str] = Field(min_length=1, max_length=12)

    @model_validator(mode="after")
    def chinese(self):
        require_chinese(
            [self.overview, self.repair_review, *self.limitations, *self.next_steps]
        )
        return self
