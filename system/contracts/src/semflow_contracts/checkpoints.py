"""Opaque native graph state with explicit engine and input identities."""

from typing import Literal
from uuid import UUID

from pydantic import ConfigDict

from semflow_contracts.common import Contract, Digest
from semflow_contracts.wire import schema_meaning


class CheckpointBundle(Contract):
    # Interface peers: runtime.checkpoints.DurableSaver._persist / restore.
    # AGENT: revise both native codecs and fresh-process recovery tests if the
    # engine format, identities or container meaning changes; never migrate a
    # running graph by merely relabelling its version or execution ID.
    model_config = ConfigDict(json_schema_extra=schema_meaning("checkpoint"))

    format: Literal["semflow.langgraph-containers/1"] = "semflow.langgraph-containers/1"
    engine: Literal["langgraph-checkpoint==4.2.0"] = "langgraph-checkpoint==4.2.0"
    execution_id: UUID
    input_digest: Digest
    storage: dict
    writes: dict
    blobs: dict
