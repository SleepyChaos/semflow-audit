from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReviewRequest(StrictModel):
    finding_ids: list[str] = Field(default_factory=list, max_length=50)
    paths: list[str] = Field(default_factory=list, max_length=50)
    discover: bool = True
    max_steps: int = Field(8, ge=1, le=16)
    max_context_chars: int = Field(40000, ge=4000, le=100000)


class DecisionRequest(StrictModel):
    status: Literal["confirmed", "excluded", "pending", "insufficient"]
    reason: str = Field(min_length=10, max_length=4000)
    evidence_ids: list[UUID] = Field(default_factory=list, max_length=40)


class RepairRequest(StrictModel):
    candidate_ids: list[UUID] = Field(min_length=1, max_length=20)
    allowed_paths: list[str] = Field(default_factory=list, max_length=30)
    validation_profile: Literal["syntax", "python_pytest", "javascript_test"] = "syntax"
    rescan: bool = True


class KnowledgeRequest(StrictModel):
    provenance: dict = Field(default_factory=dict)
    title: str = Field(min_length=1, max_length=200)
    source: str = Field(min_length=1, max_length=500)
    language: Literal["python", "javascript", "any"]
    content: str = Field(min_length=30, max_length=100000)


class RuleRequest(StrictModel):
    purpose: Literal["review_anchor", "vulnerability_detector", "framework_model"] = (
        "review_anchor"
    )
    holdout_id: str | None = Field(default=None, max_length=100)
    requirement: str = Field(min_length=10, max_length=5000)
    candidate_id: UUID | None = None
    strategy: Literal["auto", "model", "extend", "new_query"] = "auto"


class FixtureApproval(StrictModel):
    reason: str = Field(min_length=10, max_length=4000)


class RepairAcceptance(StrictModel):
    reason: str = Field(min_length=10, max_length=4000)


class ToolCall(StrictModel):
    name: Literal[
        "read_source", "search_source", "callers", "knowledge", "static_query"
    ]
    arguments: dict = Field(default_factory=dict)


class ProposedFinding(StrictModel):
    candidate_id: UUID | None = None
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=10, max_length=5000)
    assessment: Literal["supported", "excluded", "pending", "insufficient"]
    evidence_ids: list[UUID] = Field(default_factory=list, max_length=30)
    related_target: str | None = None
    weakness: str = Field(default="unknown", pattern=r"^(unknown|CWE-[0-9]+)$")
    primary_location: dict | None = None


class ReviewResponse(StrictModel):
    action: Literal["tool", "final"]
    tool: ToolCall | None = None
    findings: list[ProposedFinding] = Field(default_factory=list, max_length=50)
    summary: str = Field(default="", max_length=5000)


class ProposedChange(StrictModel):
    file: str = Field(min_length=1, max_length=300)
    old_text: str = Field(min_length=1, max_length=50000)
    new_text: str = Field(max_length=50000)
    reason: str = Field(min_length=10, max_length=2000)


class RepairResponse(StrictModel):
    changes: list[ProposedChange] = Field(min_length=1, max_length=8)
    summary: str = Field(min_length=10, max_length=5000)


class TestFixture(StrictModel):
    files: dict[str, str]
    expected: list[dict] = Field(default_factory=list)


class RuleResponse(StrictModel):
    purpose: Literal["review_anchor", "vulnerability_detector", "framework_model"] = (
        "review_anchor"
    )
    title: str = Field(min_length=1, max_length=200)
    strategy: Literal["model", "extend", "new_query"]
    coverage_analysis: str = Field(min_length=10, max_length=5000)
    query: str = Field(min_length=20, max_length=50000)
    modules: dict[str, str] = Field(default_factory=dict)
    knowledge_ids: list[UUID] = Field(min_length=1, max_length=20)
    positive: TestFixture
    negative: TestFixture
