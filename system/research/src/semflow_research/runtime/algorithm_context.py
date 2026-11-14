"""Explicit dependencies shared by algorithm steps, never a platform session."""

from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from semflow_contracts.common import ArtifactRef
from semflow_contracts.rule_values import CorpusSnapshot
from semflow_contracts.runs import RunSpec

from semflow_research.runtime.artifacts import LocalArtifacts
from semflow_research.runtime.evidence import SnapshotReader
from semflow_research.runtime.ledger import LocalLedger
from semflow_research.runtime.settings import ToolSettings
from semflow_research.state.records import RecordStore
from semflow_research.state.repositories import ExecutionRecords, SourceRecords


@dataclass(frozen=True, kw_only=True)
class AlgorithmContext:
    execution_id: UUID
    spec: RunSpec
    root: Path
    source_root: Path
    workspace: Path
    baseline_directory: Path
    settings: ToolSettings
    artifacts: LocalArtifacts
    executions: LocalLedger
    records: RecordStore
    source: SnapshotReader
    control: object
    checkpoints: object
    model: object | None = None
    corpus_snapshot: CorpusSnapshot | None = None
    supplemental_rule_ids: tuple[UUID, ...] = ()
    budget_owner_id: UUID | None = None
    resources_snapshot: ArtifactRef | None = None

    @property
    def execution_records(self):
        return ExecutionRecords(self)

    @property
    def source_records(self):
        return SourceRecords(self)
