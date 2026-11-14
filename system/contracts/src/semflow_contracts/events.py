"""Typed append-only event payloads; original results remain in manifests."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, ConfigDict, Field

from semflow_contracts.actions import ApprovalRequest
from semflow_contracts.common import ArtifactRef, Contract, EntityRef
from semflow_contracts.errors import Failure
from semflow_contracts.results import ExecutionStatus, UsageEntry
from semflow_contracts.validation import ValidationReceipt
from semflow_contracts.wire import schema_meaning


class LifecyclePayload(Contract):
    type: Literal["execution_started", "execution_finished"]
    status: ExecutionStatus
    failure: Failure | None = None


class PhasePayload(Contract):
    type: Literal["phase_changed"]
    completed_units: int | None = Field(default=None, ge=0)
    planned_units: int | None = Field(default=None, ge=0)


class EntityPayload(Contract):
    type: Literal["evidence_recorded", "candidate_recorded"]
    entity: EntityRef


class ArtifactPayload(Contract):
    type: Literal["artifact_committed"]
    artifact: ArtifactRef


class ModelPayload(Contract):
    type: Literal["model_call_finished"]
    call_id: UUID
    receipt: ArtifactRef
    usage: UsageEntry


class ValidationPayload(Contract):
    type: Literal["validation_finished"]
    receipt: ValidationReceipt


class AwaitingPayload(Contract):
    type: Literal["awaiting_input"]
    action: ApprovalRequest


EventPayload = Annotated[
    LifecyclePayload
    | PhasePayload
    | EntityPayload
    | ArtifactPayload
    | ModelPayload
    | ValidationPayload
    | AwaitingPayload,
    Field(discriminator="type"),
]


class EventInput(Contract):
    event_id: UUID
    execution_id: UUID
    occurred_at: AwareDatetime
    phase_code: str = Field(min_length=1)
    payload: EventPayload


class ExecutionEvent(EventInput):
    model_config = ConfigDict(json_schema_extra=schema_meaning("event"))

    schema_version: Literal["semflow.research.event/1.0"] = "semflow.research.event/1.0"
    seq: int = Field(ge=1)
