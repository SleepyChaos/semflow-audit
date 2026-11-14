"""Web worker adapter; all discovery computation belongs to research public APIs."""

from uuid import UUID

from semflow_contracts.runs import validate_spec
from semflow_research.public import discovery
from semflow_research.public.implementation import code_digest
from semflow_research.public.runtime import ExecutionCancelled, ToolSettings, prepare
from sqlmodel import Session, select

from app.core.audit_config import audit_settings
from app.core.db import engine
from app.domain.audit import AuditError
from app.persistence.audit_models import AuditRun
from app.persistence.stage_models import StageRun
from app.research_bridge.models import ResearchBinding
from app.research_bridge.projection import project
from app.research_bridge.requests import freeze_stage, research_root


def binding_for(stage_id):
    with Session(engine) as session:
        return session.exec(
            select(ResearchBinding).where(
                ResearchBinding.stage_id == UUID(str(stage_id))
            )
        ).first()


def execute_bound(stage_id, *, model=None):
    with Session(engine) as session:
        binding = session.exec(
            select(ResearchBinding)
            .where(ResearchBinding.stage_id == UUID(str(stage_id)))
            .with_for_update()
        ).one()
        stage = session.get(StageRun, binding.stage_id)
        audit = session.get(AuditRun, stage.audit_id)
        if not binding.request:
            spec, resources = freeze_stage(binding, stage, audit, session=session)
            session.add(binding)
            session.commit()
        else:
            # WIRE-RECV:research.run — peer: requests.freeze_stage.
            # AGENT: never replace a frozen request with current UI inputs,
            # defaults or settings after a delivery/restart; historical tasks have no binding.
            spec = validate_spec(binding.request)
            resources = ToolSettings.model_validate(binding.resources)
            resources = resources.model_copy(
                update={"AI_API_KEY": audit_settings.AI_API_KEY}
            )

    def active(_execution_id):
        with Session(engine) as db:
            current = db.get(StageRun, UUID(str(stage_id)))
            parent = db.get(AuditRun, current.audit_id)
            if current.status == "cancelled" or parent.status == "cancelled":
                raise ExecutionCancelled("平台已请求取消，科研执行在安全边界停止")

    context = prepare(
        spec,
        root=research_root(),
        settings=resources,
        model=model,
        control_guard=active,
    )
    if spec.implementation.code_digest != code_digest():
        raise AuditError(
            "已绑定科研实现发生变化，请创建新执行；不重放旧任务", code="integrity_error"
        )
    result = discovery.execute(spec, context)
    with Session(engine) as session:
        binding = session.exec(
            select(ResearchBinding)
            .where(ResearchBinding.stage_id == UUID(str(stage_id)))
            .with_for_update()
        ).one()
        return project(session, binding, result, root=research_root())


def reconcile_bound(stage_id):
    """Finish a committed kernel result after a platform projection interruption."""
    from semflow_research.public.runs import inspect

    with Session(engine) as session:
        binding = session.exec(
            select(ResearchBinding)
            .where(ResearchBinding.stage_id == UUID(str(stage_id)))
            .with_for_update()
        ).first()
        if binding is None or not binding.request or binding.manifest is not None:
            return None
        result = inspect(binding.execution_id, root=research_root())
        if result is None or result.execution_status not in {
            "completed",
            "failed",
            "cancelled",
            "interrupted",
        }:
            return None  # Never take over or replay an unknown running model call.
        return project(session, binding, result, root=research_root())
