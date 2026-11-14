"""Durable adapter for the pinned LangGraph checkpoint engine.

Graph execution and interrupt/resume remain LangGraph responsibilities. This
adapter persists its typed byte containers as JSON, never Python pickle. It is
bound to one execution and frozen input digest; incompatible engine formats fail.
"""

import base64
import os
import threading
from collections import defaultdict
from importlib.metadata import version
from pathlib import Path
from tempfile import NamedTemporaryFile

from langgraph.checkpoint.memory import InMemorySaver
from semflow_contracts.checkpoints import CheckpointBundle
from semflow_contracts.common import ArtifactRef, canonical_bytes
from semflow_contracts.errors import ResearchError


def encode(value):
    if isinstance(value, bytes):
        return {"type": "bytes", "value": base64.b64encode(value).decode()}
    if isinstance(value, tuple):
        return {"type": "tuple", "value": [encode(v) for v in value]}
    if isinstance(value, dict):
        return {
            "type": "map",
            "value": [[encode(k), encode(v)] for k, v in value.items()],
        }
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise ResearchError("checkpoint_invalid", "Unsupported checkpoint container")


def decode(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if not isinstance(value, dict):
        raise ResearchError("checkpoint_invalid", "Invalid checkpoint primitive")
    if set(value) != {"type", "value"}:
        raise ResearchError("checkpoint_invalid", "Invalid checkpoint container")
    if value["type"] == "bytes":
        return base64.b64decode(value["value"], validate=True)
    if value["type"] == "tuple":
        return tuple(decode(v) for v in value["value"])
    if value["type"] == "map":
        return {decode(k): decode(v) for k, v in value["value"]}
    raise ResearchError("checkpoint_invalid", "Unknown checkpoint container")


class DurableSaver(InMemorySaver):
    def __init__(self, *, artifacts, execution_id, input_digest, pointer: Path):
        if version("langgraph-checkpoint") != "4.2.0":
            raise ResearchError(
                "unsupported_version",
                "Checkpoint engine must match the pinned adapter version",
            )
        super().__init__()
        self.artifacts, self.execution_id = artifacts, execution_id
        self.input_digest, self.pointer = input_digest, pointer
        self._guard = threading.RLock()
        self.latest = None
        if pointer.exists():
            self.latest = ArtifactRef.model_validate_json(pointer.read_bytes())
            self.restore(self.latest)

    def restore(self, ref):
        # WIRE-RECV:research.checkpoint — peer: DurableSaver._persist.
        # AGENT: execution, frozen input and engine format must match before native resume.
        # AGENT: pair changes with _persist and CheckpointBundle, including the
        # pinned engine, typed containers, execution and immutable input digest.
        if (
            ref.kind != "checkpoint"
            or ref.owner_execution_id != self.execution_id
            or ref.schema_version != "semflow.langgraph-containers/1"
        ):
            raise ResearchError(
                "checkpoint_invalid",
                "Checkpoint reference kind, owner or format does not match",
            )
        body = CheckpointBundle.model_validate_json(self.artifacts.read(ref))
        if (
            body.execution_id != self.execution_id
            or body.input_digest != self.input_digest
        ):
            raise ResearchError(
                "checkpoint_invalid",
                "Checkpoint belongs to different inputs or execution",
            )
        storage = decode(body.storage)
        writes, blobs = decode(body.writes), decode(body.blobs)
        if any(thread != str(self.execution_id) for thread in storage) or any(
            key[0] != str(self.execution_id) for key in (*writes, *blobs)
        ):
            raise ResearchError(
                "checkpoint_invalid",
                "Native checkpoint contains another execution thread",
            )
        self.storage = defaultdict(lambda: defaultdict(dict))
        for thread, namespaces in storage.items():
            self.storage[thread] = defaultdict(dict, namespaces)
        self.writes = defaultdict(dict, writes)
        self.blobs = blobs

    def _persist(self):
        # WIRE-SEND:research.checkpoint — peer: DurableSaver.restore.
        # These bytes are a checkpoint identity, never approval of changed rule fixtures.
        # AGENT: update restore and CheckpointBundle together if this changes.
        data = CheckpointBundle(
            execution_id=self.execution_id,
            input_digest=self.input_digest,
            storage=encode(dict(self.storage)),
            writes=encode(dict(self.writes)),
            blobs=encode(self.blobs),
        )
        ref = self.artifacts.commit(
            canonical_bytes(data), kind="checkpoint", schema_version=data.format
        )
        self.pointer.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with NamedTemporaryFile(dir=self.pointer.parent, delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(ref.model_dump_json().encode())
                stream.flush()
                os.fsync(stream.fileno())
            temporary.replace(self.pointer)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        self.latest = ref

    def put(self, config, checkpoint, metadata, new_versions):
        with self._guard:
            self._require_scope(config)
            result = super().put(config, checkpoint, metadata, new_versions)
            self._persist()
            return result

    def put_writes(self, config, writes, task_id, task_path=""):
        with self._guard:
            self._require_scope(config)
            super().put_writes(config, writes, task_id, task_path)
            self._persist()

    def delete_thread(self, thread_id):
        raise ResearchError(
            "execution_conflict",
            "Scientific checkpoint history is retained; retry creates a new execution",
        )

    def _require_scope(self, config):
        if config.get("configurable", {}).get("thread_id") != str(self.execution_id):
            raise ResearchError(
                "identity_mismatch",
                "Checkpoint thread must match its scientific execution",
            )
