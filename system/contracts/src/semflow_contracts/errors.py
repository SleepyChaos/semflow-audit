"""Stable failure codes shared by transport-independent research entry points."""

from typing import Literal

from pydantic import Field

from semflow_contracts.common import ArtifactRef, Contract

FailureCode = Literal[
    "invalid_contract",
    "unsupported_version",
    "unsupported_operation",
    "identity_mismatch",
    "integrity_error",
    "evidence_invalid",
    "target_not_authorized",
    "approval_required",
    "approval_stale",
    "tool_unavailable",
    "tool_failed",
    "parse_failed",
    "model_unavailable",
    "model_output_invalid",
    "budget_exhausted",
    "resource_exhausted",
    "cancelled",
    "checkpoint_invalid",
    "execution_conflict",
    "external_outcome_unknown",
    "internal_error",
]
FailureCategory = Literal[
    "input", "identity", "integrity", "tool", "model", "budget", "control", "internal"
]


class Failure(Contract):
    code: FailureCode
    category: FailureCategory
    message: str = Field(min_length=1)
    retryable: bool
    phase: str = Field(min_length=1)
    detail: ArtifactRef | None = None


class ResearchError(Exception):
    def __init__(
        self, code: FailureCode, message: str, *, detail: ArtifactRef | None = None
    ):
        self.code = code
        self.detail = detail
        super().__init__(message)
