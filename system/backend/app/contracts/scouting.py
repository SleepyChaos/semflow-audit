"""Independent source hypotheses, never confirmed vulnerabilities."""

from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from app.contracts.review import PrimaryLocation
from app.contracts.stages import StrictModel, ToolCall


class ScoutRequest(StrictModel):
    continuation_from_id: UUID | None = None
    paths: list[str] = Field(default_factory=list, max_length=50)
    inspection_paths: list[str] = Field(default_factory=list, max_length=50)
    max_units: int = Field(0, ge=0, le=100, description="0 inspects all eligible windows")
    include_third_party: bool = False
    steps_per_unit: int = Field(3, ge=1, le=6)
    window_lines: int = Field(100, ge=20, le=150)
    max_context_chars: int = Field(30000, ge=4000, le=60000)


class ScoutFinding(StrictModel):
    title: str = Field(min_length=1, max_length=200)
    weakness: str = Field(default="unknown", pattern=r"^(unknown|CWE-[0-9]+)$")
    primary_location: PrimaryLocation
    security_condition: str = Field(min_length=10, max_length=1500)
    observation: str = Field(min_length=10, max_length=2000)
    missing_premises: list[str] = Field(default_factory=list, max_length=10)
    evidence_ids: list[UUID] = Field(min_length=1, max_length=20)


class ScoutResponse(StrictModel):
    action: Literal["tool", "final"]
    tool: ToolCall | None = None
    findings: list[ScoutFinding] = Field(default_factory=list, max_length=8)
    scope_summary: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def action_contract(self):
        if self.action == "tool" and (self.tool is None or self.findings):
            raise ValueError("Tool request must not include findings")
        if self.action == "final" and self.tool is not None:
            raise ValueError("Final cannot contain a tool")
        return self


class TaskCheck(StrictModel):
    task_id: str
    status: Literal["investigated", "unknown", "not_applicable"]
    reason: str = Field(min_length=10, max_length=600)
    evidence_ids: list[UUID] = Field(default_factory=list, max_length=12)


class ScoutResponseV4(ScoutResponse):
    findings: list[ScoutFinding] = Field(default_factory=list, max_length=16)
    task_checks: list[TaskCheck] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def complete_task_record(self):
        if self.action == "tool" and self.task_checks:
            raise ValueError("Tool responses cannot assert completed task checks")
        if self.action == "final" and not self.task_checks:
            raise ValueError("Final requires task checks; unknown is allowed")
        return self


class FinalScoutResponseV4(ScoutResponseV4):
    action: Literal["final"] = "final"
    tool: None = None


class CompactTaskCheck(TaskCheck):
    reason: str = Field(min_length=10, max_length=240)


class FocusedFinding(ScoutFinding):
    security_condition: str = Field(min_length=10, max_length=600)
    observation: str = Field(min_length=10, max_length=1000)


class ScoutResponseV5(ScoutResponseV4):
    findings: list[FocusedFinding] = Field(default_factory=list, max_length=12)
    task_checks: list[CompactTaskCheck] = Field(default_factory=list, max_length=8)


class FinalScoutResponseV5(ScoutResponseV5):
    action: Literal["final"] = "final"
    tool: None = None
