"""Infrastructure is passed per execution, never fetched from platform globals."""

from pathlib import Path
from typing import Protocol, TypeVar
from uuid import UUID

from pydantic import BaseModel
from semflow_contracts.common import ArtifactKind, ArtifactRef, SourceSnapshot
from semflow_contracts.events import EventInput, ExecutionEvent
from semflow_contracts.evidence import EvidenceRecord
from semflow_contracts.results import ResultEnvelope
from semflow_contracts.runs import ModelProfile, PromptSnapshot, RunSpec

Response = TypeVar("Response", bound=BaseModel)


class ArtifactStore(Protocol):
    def commit(
        self,
        data: bytes,
        *,
        kind: ArtifactKind,
        schema_version: str,
        media_type: str = "application/json",
    ) -> ArtifactRef: ...
    def read(self, ref: ArtifactRef) -> bytes: ...


class SourceReader(Protocol):
    snapshot: SourceSnapshot

    def read(self, path: str, start_line: int, end_line: int) -> EvidenceRecord: ...
    def validate(self, evidence: EvidenceRecord) -> None: ...


class ExecutionStore(Protocol):
    def create(self, spec: RunSpec) -> None: ...
    def claim(self, execution_id: UUID) -> bool: ...
    def append_event(self, event: EventInput) -> ExecutionEvent: ...
    def publish(
        self, result: ResultEnvelope, *, expected_revision: int
    ) -> ResultEnvelope: ...
    def inspect(self, execution_id: UUID) -> ResultEnvelope | None: ...


class ModelProvider(Protocol):
    def generate(
        self,
        *,
        profile: ModelProfile,
        prompts: tuple[PromptSnapshot, ...],
        payload: BaseModel,
        schema: type[Response],
        call_id: UUID,
    ) -> Response: ...


class ControlPort(Protocol):
    def check_active(self, execution_id: UUID) -> None:
        """Raise a typed cancellation/revocation error at a safe boundary."""
        ...


class CheckpointStore(Protocol):
    def saver(self, execution_id: UUID, graph_version: str):
        """Return a context manager for the selected framework checkpoint saver."""
        ...


class ResourceResolver(Protocol):
    def tool_path(self, profile: str) -> Path: ...
    def secret(self, profile: str) -> str: ...
