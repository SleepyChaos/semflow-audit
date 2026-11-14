"""Freeze a platform human decision for the existing research control boundary."""

from semflow_contracts.actions import ControlCommand
from semflow_contracts.evidence import ActorRef
from semflow_research.public.actions import approve
from semflow_research.public.rule_results import read_projection
from semflow_research.public.runs import inspect, revision

from app.domain.audit import AuditError
from app.research_bridge.requests import research_root
from app.research_bridge.rule_integrity import verify_confirmation


def approval_command(session, binding, stage, rule, actor_id, reason):
    verify_confirmation(session, stage)
    waiting = inspect(binding.execution_id, root=research_root())
    if (
        waiting is None
        or waiting.pending_action is None
        or waiting.execution_status != "awaiting_input"
    ):
        raise AuditError("规则科研执行不在批准门", code="execution_conflict")
    view = read_projection(waiting, root=research_root())
    if (rule.query, rule.modules, rule.dependencies, rule.fixtures) != (
        view.query,
        view.modules,
        view.dependencies,
        view.fixtures,
    ):
        raise AuditError("平台查询/样例不再匹配原审批产物", code="integrity_error")
    # WIRE-SEND:research.control — peer: rule_runtime.execute_bound / rules.resume.
    # AGENT: persist this exact checkpoint/subject/revision decision before
    # publishing the resume job. A new worker must not reconstruct approval.
    decision = approve(
        waiting.pending_action,
        actor=ActorRef(kind="human", id=str(actor_id)),
        approved=True,
        reason=reason,
    )
    return ControlCommand(
        command_id=decision.decision_id,
        execution_id=binding.execution_id,
        action="resume",
        expected_revision=revision(binding.execution_id, root=research_root()),
        checkpoint_digest=waiting.pending_action.checkpoint.sha256,
        approval=decision,
        reason=reason,
    )
