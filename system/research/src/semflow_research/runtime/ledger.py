"""Local SQLite execution ledger; filesystem commits precede visible pointers."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from pydantic import BaseModel
from semflow_contracts.common import ArtifactRef, canonical_bytes, digest
from semflow_contracts.errors import ResearchError
from semflow_contracts.events import EventInput, ExecutionEvent, LifecyclePayload
from semflow_contracts.results import ResultEnvelope, ResultManifest
from semflow_contracts.runs import RunSpec, validate_spec

from semflow_research.runtime.artifacts import LocalArtifacts


def input_artifacts(value: BaseModel) -> tuple[ArtifactRef, ...]:
    found = []

    def visit(item):
        if isinstance(item, ArtifactRef):
            found.append(item)
        elif isinstance(item, BaseModel):
            for nested in item.__dict__.values():
                visit(nested)
        elif isinstance(item, (tuple, list)):
            for nested in item:
                visit(nested)

    visit(value)
    return tuple(found)


class LocalLedger:
    def __init__(self, root: Path):
        if root.is_symlink():
            raise ResearchError("integrity_error", "Ledger root cannot be a symlink")
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = self.root / "executions.sqlite3"
        if self.path.is_symlink():
            raise ResearchError("integrity_error", "Ledger file cannot be a symlink")
        with self._connect() as db:
            db.executescript(
                "CREATE TABLE IF NOT EXISTS executions ("
                "id TEXT PRIMARY KEY, spec TEXT NOT NULL, input_digest TEXT NOT NULL, "
                "spec_ref TEXT NOT NULL, status TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 0, "
                "manifest_ref TEXT);"
                "CREATE TABLE IF NOT EXISTS events (execution_id TEXT NOT NULL "
                "REFERENCES executions(id), event_id TEXT NOT NULL, seq INTEGER NOT NULL, "
                "input TEXT NOT NULL, event TEXT NOT NULL, "
                "PRIMARY KEY(execution_id, event_id), UNIQUE(execution_id, seq));"
                "CREATE TABLE IF NOT EXISTS execution_children ("
                "parent_id TEXT NOT NULL REFERENCES executions(id), role TEXT NOT NULL, "
                "child_id TEXT NOT NULL UNIQUE REFERENCES executions(id), input_digest TEXT NOT NULL, "
                "PRIMARY KEY(parent_id, role));"
            )

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        try:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys = ON")
            with db:
                yield db
        finally:
            db.close()

    def _row(self, db, execution_id):
        row = db.execute(
            "SELECT * FROM executions WHERE id = ?", (str(execution_id),)
        ).fetchone()
        if row is None:
            raise ResearchError("identity_mismatch", "Execution is not registered")
        return row

    def _store(self, row) -> LocalArtifacts:
        frozen = json.loads(row["spec"])
        spec = validate_spec(frozen)
        # Historical receipts bind the JSON that was actually saved. New optional
        # schema defaults must not rewrite its digest while reading history.
        # Execution creation/resume still compares today's fully expanded spec
        # and rejects semantic drift; use the original version or a new attempt.
        if str(spec.execution_id) != row["id"] or digest(frozen) != row["input_digest"]:
            raise ResearchError(
                "integrity_error", "Registered execution inputs were modified"
            )
        own = LocalArtifacts(self.root / "artifacts", spec.execution_id)
        if own.read(
            ArtifactRef.model_validate_json(row["spec_ref"])
        ) != canonical_bytes(frozen):
            raise ResearchError(
                "integrity_error", "Frozen input artifact does not match the ledger"
            )
        from semflow_research.runtime.input_capabilities import authorize_spec_bundles

        return authorize_spec_bundles(
            LocalArtifacts(
                self.root / "artifacts",
                UUID(row["id"]),
                upstream=input_artifacts(spec) + self._child_refs(row),
            ),
            spec,
        )

    def _child_refs(self, row):
        from semflow_research.runtime.children import published_child_refs

        with self._connect() as db:
            return published_child_refs(self, db, row)

    def create(self, spec: RunSpec) -> None:
        spec = validate_spec(spec)
        serialized = canonical_bytes(spec)
        store = LocalArtifacts(self.root / "artifacts", spec.execution_id)
        ref = store.commit(
            serialized, kind="run_spec", schema_version=spec.schema_version
        )
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute(
                "SELECT * FROM executions WHERE id = ?", (str(spec.execution_id),)
            ).fetchone()
            if existing:
                if existing["input_digest"] != digest(spec):
                    raise ResearchError(
                        "execution_conflict",
                        "Execution ID already has different inputs",
                    )
                self._store(existing)
                return
            db.execute(
                "INSERT INTO executions(id, spec, input_digest, spec_ref, status) VALUES(?, ?, ?, ?, ?)",
                (
                    str(spec.execution_id),
                    serialized.decode(),
                    digest(spec),
                    ref.model_dump_json(),
                    "created",
                ),
            )

    def _append(self, db, event: EventInput) -> ExecutionEvent:
        serialized = canonical_bytes(event).decode()
        old = db.execute(
            "SELECT input, event FROM events WHERE execution_id = ? AND event_id = ?",
            (str(event.execution_id), str(event.event_id)),
        ).fetchone()
        if old:
            if old["input"] != serialized:
                raise ResearchError(
                    "execution_conflict", "An event ID cannot change its payload"
                )
            return ExecutionEvent.model_validate_json(old["event"])
        if self._row(db, event.execution_id)["status"] in {
            "completed",
            "failed",
            "cancelled",
            "interrupted",
        }:
            raise ResearchError(
                "execution_conflict", "Terminal executions cannot append new events"
            )
        seq = db.execute(
            "SELECT COALESCE(MAX(seq), 0) + 1 FROM events WHERE execution_id = ?",
            (str(event.execution_id),),
        ).fetchone()[0]
        # WIRE-SEND:research.event — peer: LocalLedger.events; seq is per execution, not a delivery counter.
        # AGENT: keep wire.py and the event reader consistent when changing payload meaning.
        recorded = ExecutionEvent(**event.model_dump(), seq=seq)
        db.execute(
            "INSERT INTO events VALUES(?, ?, ?, ?, ?)",
            (
                str(event.execution_id),
                str(event.event_id),
                seq,
                serialized,
                recorded.model_dump_json(),
            ),
        )
        return recorded

    def append_event(self, event: EventInput) -> ExecutionEvent:
        event = EventInput.model_validate_json(event.model_dump_json())
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self._row(db, event.execution_id)
            if isinstance(event.payload, LifecyclePayload):
                raise ResearchError(
                    "invalid_contract",
                    "Lifecycle events are owned by the execution ledger",
                )
            store = self._store(self._row(db, event.execution_id))
            for ref in input_artifacts(event):
                store.read(ref)
            return self._append(db, event)

    def claim(self, execution_id: UUID) -> bool:
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self._store(self._row(db, execution_id))
            changed = db.execute(
                "UPDATE executions SET status = 'running' WHERE id = ? AND status = 'created'",
                (str(execution_id),),
            ).rowcount
            if changed:
                self._append(
                    db,
                    EventInput(
                        event_id=uuid4(),
                        execution_id=execution_id,
                        occurred_at=datetime.now(UTC),
                        phase_code="execution_started",
                        payload=LifecyclePayload(
                            type="execution_started", status="running"
                        ),
                    ),
                )
            return changed == 1

    def publish(
        self, result: ResultEnvelope, *, expected_revision: int
    ) -> ResultEnvelope:
        # WIRE-RECV:research.result — peer: runtime.execution.execute / kernel result builders.
        # AGENT: preserve frozen input/implementation identity and independent
        # statuses here when changing the sender, wire.py or final projections.
        result = ResultEnvelope.model_validate_json(result.model_dump_json())
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = self._row(db, result.execution_id)
            if row["revision"] != expected_revision:
                raise ResearchError(
                    "execution_conflict", "Result revision has advanced"
                )
            if row["status"] in {"completed", "failed", "cancelled", "interrupted"}:
                raise ResearchError(
                    "execution_conflict", "Terminal execution history is immutable"
                )
            allowed = {
                "created": {"failed", "cancelled"},
                "running": {
                    "running",
                    "awaiting_input",
                    "completed",
                    "failed",
                    "cancelled",
                    "interrupted",
                },
                "awaiting_input": {"awaiting_input", "cancelled", "failed"},
            }
            if result.execution_status not in allowed[row["status"]]:
                raise ResearchError(
                    "execution_conflict",
                    "Invalid result transition; resume requires explicit approval",
                )
            spec = validate_spec(json.loads(row["spec"]))
            if (
                result.input_digest != row["input_digest"]
                or (result.module, result.operation) != (spec.module, spec.operation)
                or result.implementation != spec.implementation
            ):
                raise ResearchError(
                    "identity_mismatch", "Result does not match frozen execution inputs"
                )
            if row["status"] == "created" and result.execution_status not in {
                "failed",
                "cancelled",
            }:
                raise ResearchError(
                    "execution_conflict", "Execution has not been claimed"
                )
            store = self._store(row)
            if (
                result.manifest
                and result.manifest.model_dump_json() != row["manifest_ref"]
            ):
                raise ResearchError(
                    "identity_mismatch",
                    "Result references an unrelated manifest revision",
                )
            for ref in input_artifacts(result):
                if ref != result.manifest:
                    store.read(ref)
            event = EventInput(
                event_id=uuid4(),
                execution_id=result.execution_id,
                occurred_at=datetime.now(UTC),
                phase_code=result.execution_status,
                payload={"type": "awaiting_input", "action": result.pending_action}
                if result.pending_action
                else LifecyclePayload(
                    type="execution_finished"
                    if result.execution_status
                    in {"completed", "failed", "cancelled", "interrupted"}
                    else "execution_started",
                    status=result.execution_status,
                    failure=result.failure,
                ),
            )
            final_event = self._append(db, event)
            # WIRE-SEND:research.result — peer: inspect / CLI / platform projection.
            # completed, completeness and technical validation are separate; exclude manifest to avoid a hash cycle.
            # AGENT: change wire.py and receiving projections together, never infer human acceptance.
            body = result.model_dump(mode="json", exclude={"manifest"})
            result_ref = store.commit(
                canonical_bytes(body),
                kind="result_bundle",
                schema_version=result.schema_version,
            )
            # WIRE-SEND:research.manifest — peer: inspect; revision binds exact spec/result bytes.
            # AGENT: hash or revision changes require updating the reader and recovery tests.
            manifest = ResultManifest(
                execution_id=result.execution_id,
                revision=expected_revision + 1,
                input_digest=result.input_digest,
                spec=ArtifactRef.model_validate_json(row["spec_ref"]),
                result=result_ref,
                artifacts=result.artifacts,
                final_event_seq=final_event.seq,
                previous_manifest=ArtifactRef.model_validate_json(row["manifest_ref"])
                if row["manifest_ref"]
                else None,
            )
            manifest_ref = store.commit(
                canonical_bytes(manifest),
                kind="result_manifest",
                schema_version=manifest.schema_version,
            )
            db.execute(
                "UPDATE executions SET status = ?, revision = ?, manifest_ref = ? WHERE id = ?",
                (
                    result.execution_status,
                    manifest.revision,
                    manifest_ref.model_dump_json(),
                    str(result.execution_id),
                ),
            )
        return result.model_copy(update={"manifest": manifest_ref})

    def inspect(self, execution_id: UUID) -> ResultEnvelope | None:
        with self._connect() as db:
            row = self._row(db, execution_id)
            if row["manifest_ref"] is None:
                return None
            store = self._store(row)
            manifest_ref = ArtifactRef.model_validate_json(row["manifest_ref"])
            # WIRE-RECV:research.manifest — peer: publish; validate byte identities before interpreting results.
            # AGENT: keep sender, wire.py and recovery compatibility in sync.
            manifest = ResultManifest.model_validate_json(store.read(manifest_ref))
            if (
                manifest.execution_id != execution_id
                or manifest.revision != row["revision"]
                or manifest.input_digest != row["input_digest"]
                or manifest.spec.model_dump_json() != row["spec_ref"]
            ):
                raise ResearchError(
                    "integrity_error", "Manifest identity does not match the ledger"
                )
            store.read(manifest.spec)
            # WIRE-RECV:research.result — peer: publish / kernel result builders.
            # AGENT: do not reinterpret completed as scientifically passed, confirmed or published.
            result = ResultEnvelope.model_validate_json(store.read(manifest.result))
            spec = validate_spec(json.loads(row["spec"]))
            if (
                result.execution_id != execution_id
                or result.input_digest != row["input_digest"]
                or result.execution_status != row["status"]
                or (result.module, result.operation) != (spec.module, spec.operation)
                or result.implementation != spec.implementation
            ):
                raise ResearchError(
                    "integrity_error",
                    "Published result identity does not match its execution",
                )
            for ref in input_artifacts(result):
                store.read(ref)
            from semflow_contracts.rules import RuleResult

            if isinstance(result.result, RuleResult) and result.result.diagnostics:
                from semflow_research.runtime.rule_diagnostics import read

                read(store, result.result.diagnostics, execution_id)
            from semflow_contracts.repair import RepairResult

            if isinstance(result.result, RepairResult):
                from semflow_research.runtime.repair_outputs import read_attempts

                attempts = read_attempts(
                    store,
                    result.result.attempts,
                    execution_id=result.execution_id,
                    snapshot_id=spec.source.snapshot_id,
                )
                selected = next(
                    (attempt for attempt in attempts.records if attempt.selected), None
                )
                if (
                    (selected.attempt_id if selected else None)
                    != result.result.selected_attempt_id
                    or (selected.patch if selected else None) != result.result.patch
                    or (selected.patched_source if selected else None)
                    != result.result.patched_source
                ):
                    raise ResearchError(
                        "integrity_error",
                        "Published repair selection differs from immutable attempt history",
                    )
            return result.model_copy(update={"manifest": manifest_ref})

    def events(self, execution_id: UUID) -> tuple[ExecutionEvent, ...]:
        with self._connect() as db:
            self._row(db, execution_id)
            # WIRE-RECV:research.event — peer: _append; preserve sequence and idempotent event identity.
            # AGENT: payload and ordering changes must update sender / wire.py together.
            return tuple(
                ExecutionEvent.model_validate_json(row[0])
                for row in db.execute(
                    "SELECT event FROM events WHERE execution_id = ? ORDER BY seq",
                    (str(execution_id),),
                )
            )
