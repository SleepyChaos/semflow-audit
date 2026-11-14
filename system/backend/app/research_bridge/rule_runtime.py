"""Thin rule worker: freeze, call the shared public kernel, project or resume."""

import hashlib
from uuid import UUID

from semflow_contracts.actions import ControlCommand
from semflow_contracts.runs import validate_spec
from semflow_research.public import rules
from semflow_research.public.implementation import code_digest
from semflow_research.public.runs import inspect
from semflow_research.public.runtime import ExecutionCancelled, ToolSettings, prepare
from sqlmodel import Session, select

from app.core.audit_config import ROOT, audit_settings
from app.core.db import engine
from app.domain.audit import AuditError
from app.persistence.audit_models import AuditRun
from app.persistence.stage_models import StageRun
from app.research_bridge.models import ResearchBinding
from app.research_bridge.requests import research_root
from app.research_bridge.rule_integrity import verify_confirmation
from app.research_bridge.rule_projection import project_rule
from app.research_bridge.rule_requests import freeze_rule


def execute_bound(stage_id, *, resume=False, model=None):
    with Session(engine) as session:
        binding = session.exec(
            select(ResearchBinding)
            .where(ResearchBinding.stage_id == UUID(str(stage_id)))
            .with_for_update()
        ).one()
        stage = session.get(StageRun, binding.stage_id)
        audit = session.get(AuditRun, stage.audit_id)
        if binding.request:
            published = inspect(
                binding.execution_id, root=research_root(), missing_ok=True
            )
            if published and published.execution_status in {
                "completed",
                "failed",
                "cancelled",
                "interrupted",
            }:
                return project_rule(session, binding, published, root=research_root())
        if not binding.request:
            if resume:
                raise AuditError(
                    "规则尚无冻结请求，不能恢复", code="execution_conflict"
                )
            with session.no_autoflush:
                spec = freeze_rule(binding, stage, audit, session)
            session.add(binding)
            session.add(stage)
            session.commit()
        else:
            spec = validate_spec(binding.request)
        verify_confirmation(session, stage)
        settings = ToolSettings.model_validate(binding.resources).model_copy(
            update={"AI_API_KEY": audit_settings.AI_API_KEY}
        )
        command = None
        if resume:
            # WIRE-RECV:research.control — peer: rule_control.approval_command.
            # AGENT: only the saved human decision may advance this checkpoint;
            # do not synthesize a true boolean or invoke a legacy graph.
            if "research_control_command" not in stage.result:
                raise AuditError(
                    "缺少已持久化的科研恢复命令", code="execution_conflict"
                )
            command = ControlCommand.model_validate(
                stage.result["research_control_command"]
            )
    if (
        spec.implementation.code_digest != code_digest()
        or spec.implementation.dependency_lock_digest
        != hashlib.sha256((ROOT / "system/uv.lock").read_bytes()).hexdigest()
    ):
        raise AuditError(
            "规则科研实现或依赖锁变化，请创建新执行", code="integrity_error"
        )

    def active(_execution_id):
        with Session(engine) as db:
            current = db.get(StageRun, UUID(str(stage_id)))
            audit = db.get(AuditRun, current.audit_id)
            if current.status == "cancelled" or audit.status == "cancelled":
                raise ExecutionCancelled("规则已请求取消，在安全边界停止")
            verify_confirmation(db, current)

    context = prepare(
        spec, root=research_root(), settings=settings, model=model, control_guard=active
    )
    result = (
        rules.resume(spec, context, command) if resume else rules.execute(spec, context)
    )
    with Session(engine) as session:
        binding = session.exec(
            select(ResearchBinding)
            .where(ResearchBinding.stage_id == UUID(str(stage_id)))
            .with_for_update()
        ).one()
        return project_rule(session, binding, result, root=research_root())


def reconcile_bound(stage_id):
    with Session(engine) as session:
        binding = session.exec(
            select(ResearchBinding)
            .where(ResearchBinding.stage_id == UUID(str(stage_id)))
            .with_for_update()
        ).first()
        if binding is None or not binding.request:
            return None
        result = inspect(binding.execution_id, root=research_root(), missing_ok=True)
        if result is None or result.execution_status not in {
            "awaiting_input",
            "completed",
            "failed",
            "cancelled",
            "interrupted",
        }:
            return None
        return project_rule(session, binding, result, root=research_root())
