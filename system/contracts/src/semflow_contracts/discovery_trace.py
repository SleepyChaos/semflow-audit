"""Method-specific diagnostics for compatibility views, not an entity protocol."""

from typing import Literal
from uuid import UUID

from pydantic import Field

from semflow_contracts.common import Contract, Digest


class DiscoveryTrace(Contract):
    # Peers: discovery_outputs.export / public.discovery.read_result and platform
    # projection. AGENT: state is method-version-specific diagnostic data; do not
    # treat its model conclusions as human decisions, or reuse platform identities.
    schema_version: Literal["semflow.discovery-trace/1"] = "semflow.discovery-trace/1"
    execution_id: UUID
    snapshot_id: UUID
    source_digest: Digest
    method_version: str
    state: dict = Field(default_factory=dict)
    usage: dict = Field(default_factory=dict)
    model_calls: tuple[dict, ...] = ()
