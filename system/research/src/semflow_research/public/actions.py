"""Construct explicit human decisions; persistence/execution belongs to the caller."""

from datetime import UTC, datetime
from uuid import uuid4

from semflow_contracts.actions import ApprovalDecision, ApprovalRequest
from semflow_contracts.evidence import ActorRef


def approve(
    request: ApprovalRequest, *, actor: ActorRef, approved: bool, reason: str
) -> ApprovalDecision:
    request = ApprovalRequest.model_validate_json(request.model_dump_json())
    # WIRE-SEND:research.approval — peer: runtime.approvals.validate_approval.
    # AGENT: send exactly the displayed action and frozen subject digest; changing
    # either requires updating the receiver, schema and stale-approval tests.
    return ApprovalDecision(
        decision_id=uuid4(),
        action_id=request.action_id,
        actor=actor,
        approved=approved,
        reason=reason,
        subject_digest=request.subject_digest,
        created_at=datetime.now(UTC),
    )


def decision_command(execution_id, *, root, actor, approved, reason):
    """Freeze one explicit local human decision against the current pending action."""
    from semflow_contracts.actions import ControlCommand
    from semflow_contracts.errors import ResearchError

    from semflow_research.public.runs import inspect, revision

    waiting = inspect(execution_id, root=root)
    if waiting is None or waiting.pending_action is None:
        raise ResearchError(
            "execution_conflict", "Rule execution is not awaiting a decision"
        )
    decision = approve(
        waiting.pending_action, actor=actor, approved=approved, reason=reason
    )
    return ControlCommand(
        command_id=uuid4(),
        execution_id=execution_id,
        action="resume",
        expected_revision=revision(execution_id, root=root),
        checkpoint_digest=waiting.pending_action.checkpoint.sha256,
        approval=decision,
        reason=reason,
    )


def save_command(command, *, root):
    from semflow_contracts.common import canonical_bytes
    from semflow_contracts.errors import ResearchError

    directory = root / "decisions" / str(command.execution_id)
    if any(path.is_symlink() for path in (root, root / "decisions", directory)):
        raise ResearchError("integrity_error", "Decision directory cannot be a symlink")
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (str(command.command_id) + ".json")
    with path.open("xb") as stream:
        stream.write(canonical_bytes(command))
    return path


def load_command(path):
    from semflow_contracts.actions import ControlCommand

    return ControlCommand.model_validate_json(path.read_bytes())
