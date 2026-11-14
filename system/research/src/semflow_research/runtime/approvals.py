"""Validate operator intent against exact saved graph and artifact identities."""

from semflow_contracts.actions import (
    ApprovalDecision,
    ApprovalRequest,
    ControlCommand,
    approval_subject_digest,
)
from semflow_contracts.errors import ResearchError


def validate_approval(
    request: ApprovalRequest, decision: ApprovalDecision, *, artifacts, checkpoint
):
    # WIRE-RECV:research.approval — peer: public.actions.approve.
    # AGENT: preserve the human/action/byte identities and pair this gate with
    # sender + actions.py; a positive decision never proves technical correctness.
    request = ApprovalRequest.model_validate_json(request.model_dump_json())
    decision = ApprovalDecision.model_validate_json(decision.model_dump_json())
    if (
        decision.action_id != request.action_id
        or decision.subject_digest != request.subject_digest
    ):
        raise ResearchError(
            "approval_stale", "Approval refers to another action or frozen subject"
        )
    if decision.created_at < request.created_at:
        raise ResearchError("approval_stale", "Approval predates its request")
    if (
        checkpoint != request.checkpoint
        or approval_subject_digest(request.subject_refs) != request.subject_digest
    ):
        raise ResearchError(
            "approval_stale", "Approval checkpoint or subject identity changed"
        )
    artifacts.read(request.checkpoint)
    for ref in request.subject_refs:
        artifacts.read(ref)
    return decision.approved


def validate_resume(
    command: ControlCommand, result, *, revision, artifacts, checkpoint
):
    # WIRE-RECV:research.control — peer: caller ControlCommand producer.
    # AGENT: resume retains this execution and pending action; retry creates a
    # different execution. Do not bypass byte/revision checks after a UI click.
    command = ControlCommand.model_validate_json(command.model_dump_json())
    if (
        command.action != "resume"
        or result.execution_status != "awaiting_input"
        or result.pending_action is None
    ):
        raise ResearchError(
            "execution_conflict", "Resume requires a pending input action"
        )
    if (
        command.execution_id != result.execution_id
        or command.expected_revision != revision
    ):
        raise ResearchError(
            "execution_conflict", "Execution or revision advanced before resume"
        )
    if checkpoint.sha256 != command.checkpoint_digest:
        raise ResearchError("approval_stale", "Resume checkpoint identity changed")
    return validate_approval(
        result.pending_action,
        command.approval,
        artifacts=artifacts,
        checkpoint=checkpoint,
    )
