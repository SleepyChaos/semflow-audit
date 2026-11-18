"""Diagnostic continuation plan carried by the discovery trace."""

from typing import Literal

from pydantic import Field, model_validator

from semflow_contracts.common import Contract, RelativePath


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
