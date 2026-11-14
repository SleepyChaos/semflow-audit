"""A new scout execution continues a frozen map, never an upstream workspace."""

from typing import Literal
from uuid import UUID

from semflow_contracts.common import ArtifactRef, BundleRef, Contract, Digest
from semflow_contracts.modelio.scouting import ScoutRequest


class ScoutContinuation(Contract):
    # Peers: public.scout_continuation.capture -> runtime.scout_continuation.receive.
    # AGENT: map, original receipt, hypotheses and completed windows are one
    # frozen input. Continue with a new execution ID; do not reinterpret its
    # inherited IDs as newly generated findings or reset unknown premises.
    schema_version: Literal["semflow.scout-continuation/1"] = (
        "semflow.scout-continuation/1"
    )
    previous_execution_id: UUID
    snapshot_id: UUID
    source_digest: Digest
    method_version: str
    code_digest: Digest
    dependency_lock_digest: Digest
    manifest: ArtifactRef
    project_map: ArtifactRef
    trace: ArtifactRef
    candidates: BundleRef
    evidence: BundleRef
    native_inputs: ScoutRequest
