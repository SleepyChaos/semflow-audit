"""Caller-owned approvals and version-bound execution control."""

from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, ConfigDict, Field, model_validator

from semflow_contracts.common import ArtifactRef, Contract, Digest, digest
from semflow_contracts.evidence import ActorRef
from semflow_contracts.wire import schema_meaning


class ApprovalRequest(Contract):
    model_config = ConfigDict(json_schema_extra=schema_meaning("approval"))

    action_id: UUID
    kind: Literal["approve_rule_fixtures", "review_suite"]
    execution_id: UUID
    checkpoint: ArtifactRef
    subject_refs: tuple[ArtifactRef, ...] = Field(min_length=1)
    subject_digest: Digest = Field(
        description="SHA-256 of canonical JSON for the ordered, complete subject_refs; covers artifact producer, schema, path and exact byte digest."
    )
    required_actor: Literal["human"] = "human"
    reason_schema_version: Literal["1"] = "1"
    created_at: AwareDatetime

    @model_validator(mode="after")
    def frozen_subject(self):
        if (
            self.checkpoint.kind != "checkpoint"
            or self.checkpoint.owner_execution_id != self.execution_id
        ):
            raise ValueError("Approval checkpoint must belong to its execution")
        if self.subject_digest != approval_subject_digest(self.subject_refs):
            raise ValueError(
                "Approval subject digest must bind every frozen subject reference"
            )
        return self


def approval_subject_digest(refs: tuple[ArtifactRef, ...]) -> str:
    # Interface peers: public.actions.approve and runtime.approvals.validate_approval.
    # AGENT: ordering and the full ArtifactRef identity are significant; update
    # producer and receiver together instead of switching to just query text.
    return digest([ref.model_dump(mode="json") for ref in refs])


class ApprovalDecision(Contract):
    # Interface peers: public.actions.approve -> runtime.approvals.validate_approval.
    # AGENT: an affirmative decision binds this action/subject only; it grants no
    # approval for regenerated fixtures, another checkpoint or technical success.
    model_config = ConfigDict(json_schema_extra=schema_meaning("approval"))

    decision_id: UUID
    action_id: UUID
    actor: ActorRef
    approved: bool
    reason: str = Field(min_length=10, max_length=4000)
    subject_digest: Digest
    created_at: AwareDatetime

    @model_validator(mode="after")
    def human_only(self):
        if self.actor.kind != "human":
            raise ValueError("Fixture approval requires an explicit human actor")
        return self


class ControlCommand(Contract):
    model_config = ConfigDict(json_schema_extra=schema_meaning("control"))

    command_id: UUID
    execution_id: UUID
    action: Literal["resume", "cancel"]
    expected_revision: int = Field(ge=0)
    checkpoint_digest: Digest | None = None
    approval: ApprovalDecision | None = None
    reason: str = Field(min_length=1, max_length=4000)

    @model_validator(mode="after")
    def resume_requires_checkpoint(self):
        if self.action == "resume" and (
            self.checkpoint_digest is None or self.approval is None
        ):
            raise ValueError("Resume requires the checkpoint and approval identity")
        if self.action == "cancel" and self.approval is not None:
            raise ValueError("Cancellation must not contain an approval")
        return self
