"""External worker receipts survive disposal of the mutable execution workspace."""

from typing import Literal
from uuid import UUID

from pydantic import ConfigDict, model_validator

from semflow_contracts.common import ArtifactRef, Contract, Digest, RelativePath
from semflow_contracts.wire import schema_meaning


class OpenHandsReceipt(Contract):
    # WIRE-SEND:research.openhands_receipt — peer: adapters.repair.openhands_receipts.read.
    # AGENT: preserve failed/unknown engine state independently of candidate
    # validation; every member is immutable and belongs to this execution.
    model_config = ConfigDict(json_schema_extra=schema_meaning("openhands_receipt"))
    schema_version: Literal["semflow.openhands-receipt/1"] = (
        "semflow.openhands-receipt/1"
    )
    execution_id: UUID
    policy_digest: Digest
    status: Literal["completed", "failed", "cancelled", "timed_out"]
    error_code: str | None = None
    files: dict[RelativePath, ArtifactRef]

    @model_validator(mode="after")
    def owns_files(self):
        if any(
            ref.owner_execution_id != self.execution_id for ref in self.files.values()
        ):
            raise ValueError("Worker receipt cannot contain foreign execution files")
        return self
