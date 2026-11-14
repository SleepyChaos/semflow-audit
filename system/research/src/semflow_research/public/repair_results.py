"""Public bridge codec for immutable native repair artifacts and disposable views."""

import json
from dataclasses import dataclass
from pathlib import Path

from semflow_contracts.errors import ResearchError
from semflow_contracts.repair import RepairAttempts, RepairResult

from semflow_research.runtime.artifacts import LocalArtifacts
from semflow_research.runtime.evidence import SnapshotReader
from semflow_research.runtime.ledger import LocalLedger
from semflow_research.runtime.repair_outputs import read_attempts
from semflow_research.runtime.sources import materialize


@dataclass(frozen=True)
class RepairProjection:
    attempts: RepairAttempts
    proposal: dict
    patch_bytes: bytes | None
    context_bytes: bytes
    checks: dict
    patched_source: Path | None = None


def read_projection(result: RepairResult, *, root: Path) -> RepairProjection:
    # WIRE-SEND:research.repair_attempts — peer: app.research_bridge.repair_projection.
    # AGENT: expose original bytes and explicit check names, never revalidate or
    # reinterpret syntax/model checks as an acceptance or a before/after result.
    ledger = LocalLedger(root)
    execution_id = result.attempts.owner_execution_id
    envelope = ledger.inspect(execution_id)
    if envelope is None or envelope.result != result:
        raise ResearchError(
            "integrity_error", "Only an exact published repair can be projected"
        )
    with ledger._connect() as db:
        store = ledger._store(ledger._row(db, execution_id))
    body = RepairAttempts.model_validate_json(store.read(result.attempts))
    attempts = read_attempts(
        store,
        result.attempts,
        execution_id=result.attempts.owner_execution_id,
        snapshot_id=body.snapshot_id,
    )
    selected = next((row for row in attempts.records if row.selected), None)
    if (
        (selected.attempt_id if selected else None) != result.selected_attempt_id
        or (selected.patch if selected else None) != result.patch
        or (selected.patched_source if selected else None) != result.patched_source
        or (selected.checks if selected else ()) != result.checks
    ):
        raise ResearchError(
            "integrity_error", "Selected repair differs from immutable attempt history"
        )
    checks = {}
    for receipt in result.checks:
        if receipt.raw_output is None or len(receipt.checks) != 1:
            raise ResearchError(
                "invalid_contract", "Native check requires one original named receipt"
            )
        key = receipt.checks[0].check_id
        if key in checks:
            raise ResearchError("integrity_error", "Duplicate native check identity")
        checks[key] = json.loads(store.read(receipt.raw_output))
    return RepairProjection(
        attempts=attempts,
        proposal=json.loads(store.read(selected.proposal)) if selected else {},
        patch_bytes=store.read(result.patch) if result.patch else None,
        context_bytes=store.read(result.semantic_context),
        checks=checks,
    )


def materialize_projection(
    result: RepairResult, *, root: Path, target: Path
) -> RepairProjection:
    """Rebuild a disposable view from refs; changed existing files are rejected."""
    from dataclasses import replace

    view = read_projection(result, root=root)
    patched = None
    if result.patched_source:
        patched = target / "workspace"
        materialize(
            result.patched_source,
            artifacts=LocalArtifacts(
                root / "artifacts", result.attempts.owner_execution_id
            ),
            execution_id=result.attempts.owner_execution_id,
            target=patched,
        )
    return replace(view, patched_source=patched)


def verify_projection(
    result: RepairResult, *, root: Path, target: Path, changes
) -> None:
    """Verify an existing presentation copy without repairing it during acceptance."""
    view = read_projection(result, root=root)
    if (
        view.proposal.get("changes", []) != changes
        or (target / "repair-context.json").read_bytes() != view.context_bytes
        or (
            view.patch_bytes is not None
            and (target / "repair.diff").read_bytes() != view.patch_bytes
        )
    ):
        raise ResearchError(
            "integrity_error", "Repair presentation differs from immutable artifacts"
        )
    if result.patched_source:
        SnapshotReader(
            target / "workspace",
            result.patched_source,
            result.attempts.owner_execution_id,
            LocalArtifacts(root / "artifacts", result.attempts.owner_execution_id),
        )
