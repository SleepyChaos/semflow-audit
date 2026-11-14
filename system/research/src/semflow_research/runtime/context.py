"""An execution receives all of its dependencies as an immutable context."""

from dataclasses import dataclass
from uuid import UUID

from semflow_research.runtime.ports import (
    ArtifactStore,
    CheckpointStore,
    ControlPort,
    ExecutionStore,
    ModelProvider,
    ResourceResolver,
    SourceReader,
)


@dataclass(frozen=True)
class RunContext:
    execution_id: UUID
    artifacts: ArtifactStore
    executions: ExecutionStore
    source: SourceReader
    control: ControlPort
    resources: ResourceResolver
    model: ModelProvider | None = None
    checkpoints: CheckpointStore | None = None
