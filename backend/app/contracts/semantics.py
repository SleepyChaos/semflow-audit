"""Evidence-grounded inspection contracts shared by repair and rule preparation."""

from typing import Literal

from pydantic import Field, model_validator

from app.contracts.stages import StrictModel


class ReadTool(StrictModel):
    name: Literal["read_source", "search_source", "callers", "read_document"]
    arguments: dict = Field(default_factory=dict)
    reason: str = Field(min_length=5, max_length=500)


class SemanticFact(StrictModel):
    statement: str = Field(min_length=5, max_length=1200)
    state: Literal["supported", "inferred", "unknown", "conflicting"]
    evidence_ids: list[str] = Field(default_factory=list, max_length=10)
    category: Literal["business", "security", "implementation"]
    critical: bool = False


class InspectionResponse(StrictModel):
    action: Literal["tool", "ready", "insufficient"]
    tool: ReadTool | None = None
    project_overview: str = Field(default="", max_length=1600)
    target_flow: str = Field(default="", max_length=2500)
    modification_semantics: str = Field(default="", max_length=2000)
    facts: list[SemanticFact] = Field(default_factory=list, max_length=20)
    unknowns: list[str] = Field(default_factory=list, max_length=12)

    @model_validator(mode="after")
    def consistent_action(self):
        if (self.action == "tool") != (self.tool is not None):
            raise ValueError("Only tool actions may contain a tool request")
        if self.action == "ready" and (
            not self.project_overview
            or not self.target_flow
            or not self.modification_semantics
            or not self.facts
        ):
            raise ValueError("Ready inspection needs a target flow and grounded facts")
        return self
