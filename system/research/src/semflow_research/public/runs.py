"""Read local research results without consulting a Web system instance."""

import json
from pathlib import Path
from uuid import UUID

from semflow_contracts.errors import ResearchError
from semflow_contracts.results import ResultEnvelope

from semflow_research.runtime.ledger import LocalLedger


def inspect(
    execution_id: UUID, *, root: Path, missing_ok: bool = False
) -> ResultEnvelope | None:
    if not (root / "executions.sqlite3").is_file():
        if missing_ok:
            return None
        raise ResearchError(
            "identity_mismatch", "Research execution ledger does not exist"
        )
    ledger = LocalLedger(root)
    if missing_ok:
        with ledger._connect() as db:
            if (
                db.execute(
                    "SELECT 1 FROM executions WHERE id = ?", (str(execution_id),)
                ).fetchone()
                is None
            ):
                return None
    return ledger.inspect(execution_id)


def execute(spec, *, root: Path, settings, model=None):
    """Call the selected kernel directly; no Web service or platform database."""
    from semflow_contracts.runs import validate_spec

    from semflow_research.public import discovery, repair, rules
    from semflow_research.public.runtime import prepare

    spec = validate_spec(spec)
    context = prepare(spec, root=root, settings=settings, model=model)
    return {
        "discovery": discovery.execute,
        "repair": repair.execute,
        "rules": rules.execute,
    }[spec.module](spec, context)


def cancel(command, *, root: Path):
    from semflow_research.runtime.control import LocalControl

    return LocalControl(LocalLedger(root)).request_cancel(command)


def cancellation_command(execution_id: UUID, *, root: Path):
    """Assemble the current revision-bound request without a handwritten JSON ID."""
    from uuid import uuid4

    from semflow_contracts.actions import ControlCommand

    ledger = LocalLedger(root)
    with ledger._connect() as db:
        row = ledger._row(db, execution_id)
        ledger._store(row)
        return ControlCommand(
            command_id=uuid4(),
            execution_id=execution_id,
            action="cancel",
            expected_revision=row["revision"],
            reason="Cancellation explicitly requested by the independent CLI operator",
        )


def revision(execution_id: UUID, *, root: Path) -> int:
    """Read the current immutable ledger revision for a control command."""
    ledger = LocalLedger(root)
    with ledger._connect() as db:
        return ledger._row(db, execution_id)["revision"]


def specification(execution_id: UUID, *, root: Path):
    """Read the original immutable request; resume never accepts replacement inputs."""
    from semflow_contracts.runs import validate_spec

    ledger = LocalLedger(root)
    with ledger._connect() as db:
        row = ledger._row(db, execution_id)
        ledger._store(row)
        return validate_spec(json.loads(row["spec"]))


def resume(command, *, root: Path, settings, model=None):
    from semflow_research.public import rules
    from semflow_research.public.runtime import prepare

    spec = specification(command.execution_id, root=root)
    if spec.module != "rules":
        raise ResearchError(
            "unsupported_operation",
            "Only rule fixture approval continuation is connected",
        )
    return rules.resume(
        spec, prepare(spec, root=root, settings=settings, model=model), command
    )


def capture_source(directory: Path, *, root: Path, owner_execution_id: UUID, languages):
    from semflow_research.runtime.artifacts import LocalArtifacts
    from semflow_research.runtime.sources import capture

    return capture(
        directory,
        artifacts=LocalArtifacts(root / "artifacts", owner_execution_id),
        languages=languages,
    )
