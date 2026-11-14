"""Per-execution cancellation requests and immutable command identities."""

from uuid import UUID

from semflow_contracts.actions import ControlCommand
from semflow_contracts.common import canonical_bytes
from semflow_contracts.errors import ResearchError

from semflow_research.domain.errors import ExecutionCancelled


class LocalControl:
    def __init__(self, ledger, parents=(), guard=None):
        self.ledger, self.parents = ledger, tuple(parents)
        self.guard = guard
        with ledger._connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS control_commands (command_id TEXT PRIMARY KEY, "
                "execution_id TEXT NOT NULL, action TEXT NOT NULL, payload TEXT NOT NULL)"
            )

    def request_cancel(self, command: ControlCommand):
        # WIRE-RECV:research.control — peer: CLI / platform action producers.
        # Cancellation is a request; only the executor can declare it stopped.
        # AGENT: pair command identity/revision changes with semflow_cli.main.dispatch
        # and actions.ControlCommand; never reinterpret a request as completion.
        command = ControlCommand.model_validate_json(command.model_dump_json())
        if command.action != "cancel":
            raise ResearchError(
                "invalid_contract", "Cancellation endpoint requires a cancel command"
            )
        raw = canonical_bytes(command).decode()
        with self.ledger._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = self.ledger._row(db, command.execution_id)
            previous = db.execute(
                "SELECT payload FROM control_commands WHERE command_id=?",
                (str(command.command_id),),
            ).fetchone()
            if previous:
                if previous[0] != raw:
                    raise ResearchError(
                        "execution_conflict", "Control command ID changed meaning"
                    )
                return
            if row["revision"] != command.expected_revision:
                raise ResearchError(
                    "execution_conflict", "Execution advanced before cancellation"
                )
            if row["status"] in {"completed", "failed", "cancelled", "interrupted"}:
                raise ResearchError(
                    "execution_conflict", "Cannot cancel a terminal execution"
                )
            db.execute(
                "INSERT INTO control_commands VALUES(?,?,?,?)",
                (
                    str(command.command_id),
                    str(command.execution_id),
                    command.action,
                    raw,
                ),
            )

    def check_active(self, execution_id: UUID):
        if self.guard is not None:
            self.guard(execution_id)
        with self.ledger._connect() as db:
            for identifier in (execution_id, *self.parents):
                if db.execute(
                    "SELECT 1 FROM control_commands WHERE execution_id=? AND action='cancel' LIMIT 1",
                    (str(identifier),),
                ).fetchone():
                    raise ExecutionCancelled(
                        "科研执行已请求取消；在安全边界停止", code="cancelled"
                    )

    def claim_resume(self, command: ControlCommand, *, checkpoint):
        """Atomically consume a revision-bound approval, then permit continuation."""
        from semflow_research.runtime.approvals import validate_resume

        command = ControlCommand.model_validate_json(command.model_dump_json())
        if command.action != "resume":
            raise ResearchError("invalid_contract", "Expected a resume command")
        raw = canonical_bytes(command).decode()
        with self.ledger._connect() as db:
            old = db.execute(
                "SELECT payload FROM control_commands WHERE command_id=?",
                (str(command.command_id),),
            ).fetchone()
            if old:
                if old[0] != raw:
                    raise ResearchError(
                        "execution_conflict", "Control command ID changed meaning"
                    )
                row = self.ledger._row(db, command.execution_id)
                if row["status"] in {"completed", "failed", "cancelled", "interrupted"}:
                    return None
                raise ResearchError(
                    "execution_conflict",
                    "Accepted resume is already in progress; do not replay it",
                )
        previous = self.ledger.inspect(command.execution_id)
        if previous is None:
            raise ResearchError("execution_conflict", "No published approval request")
        with self.ledger._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = self.ledger._row(db, command.execution_id)
            if row["status"] != "awaiting_input":
                raise ResearchError(
                    "execution_conflict", "Execution is no longer awaiting approval"
                )
            if row["manifest_ref"] != previous.manifest.model_dump_json():
                raise ResearchError(
                    "execution_conflict", "Result advanced before resume"
                )
            validate_resume(
                command,
                previous,
                revision=row["revision"],
                artifacts=self.ledger._store(row),
                checkpoint=checkpoint,
            )
            self.check_active(command.execution_id)
            db.execute(
                "INSERT INTO control_commands VALUES(?,?,?,?)",
                (str(command.command_id), str(command.execution_id), "resume", raw),
            )
            db.execute(
                "UPDATE executions SET status='running' WHERE id=? AND status='awaiting_input'",
                (str(command.execution_id),),
            )
            return row["revision"]
