"""Execution completion and validation success are independent facts."""

from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, Field, model_validator

from semflow_contracts.common import ArtifactRef, Contract, Digest, EntityRef

CheckStatus = Literal[
    "passed", "failed", "error", "not_run", "not_evaluated", "inconclusive", "stale"
]


class CheckResult(Contract):
    check_id: str = Field(min_length=1)
    category: str = Field(min_length=1)
    status: CheckStatus
    expected: ArtifactRef | None = None
    observed: ArtifactRef | None = None
    # Peers: verification_runner raw XML/log sender -> repair_outputs / repair_verify.
    # AGENT: preserve actual reports as immutable refs alongside parsed results;
    # a disposable directory path is not an evidence reference.
    evidence: tuple[ArtifactRef, ...] = ()
    reason: str | None = None


class ValidationReceipt(Contract):
    validation_id: UUID
    kind: Literal[
        "patch_application",
        "syntax",
        "project_tests",
        "rescan",
        "before_after",
        "semantic_consistency",
        "rule_compile",
        "rule_development",
        "rule_project_replay",
        "rule_holdout",
    ]
    status: CheckStatus
    subject_refs: tuple[ArtifactRef, ...] = Field(min_length=1)
    target_refs: tuple[EntityRef, ...] = ()
    identity_digest: Digest
    checks: tuple[CheckResult, ...] = ()
    tool_profile: str = Field(min_length=1)
    raw_output: ArtifactRef | None = None
    started_at: AwareDatetime | None = None
    ended_at: AwareDatetime | None = None
    meaning: str = Field(min_length=1)

    @model_validator(mode="after")
    def passed_has_evidence(self):
        if self.status == "passed" and (
            not self.checks
            or any(check.status != "passed" for check in self.checks)
            or self.raw_output is None
        ):
            raise ValueError("Passed validation requires passed checks and raw output")
        if self.started_at and self.ended_at and self.ended_at < self.started_at:
            raise ValueError("Validation ended before it started")
        return self
