from typing import Literal

from pydantic import Field

from app.contracts.stages import StrictModel


class FailureDiagnosis(StrictModel):
    category: Literal["implementation", "understanding", "environment", "inconclusive"]
    summary: str = Field(min_length=10, max_length=1600)
    violated_constraints: list[str] = Field(default_factory=list, max_length=10)
    next_action: str = Field(min_length=5, max_length=1000)
