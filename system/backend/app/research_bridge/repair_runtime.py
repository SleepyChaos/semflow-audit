"""Native repair worker adapter with platform-only projection."""

import hashlib
from uuid import UUID

from semflow_contracts.runs import validate_spec
from semflow_research.public import repair
from semflow_research.public.implementation import code_digest
from semflow_research.public.runs import inspect
from semflow_research.public.runtime import ToolSettings, prepare
from sqlmodel import Session, select

from app.core.audit_config import ROOT, audit_settings
from app.core.db import engine
from app.domain.audit import AuditError
from app.persistence.audit_models import AuditRun
from app.persistence.stage_models import StageRun
from app.research_bridge.models import ResearchBinding
from app.research_bridge.repair_projection import project_repair
from app.research_bridge.repair_requests import freeze_repair
from app.research_bridge.requests import research_root


def execute_bound(stage_id, *, model=None):
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
            if published is not None and published.execution_status in {
                "completed",
                "failed",
                "cancelled",
                "interrupted",
            }:
                return project_repair(session, binding, published, root=research_root())
        if not binding.request:
            with session.no_autoflush:
                if stage.kind == "verification_suite":
                    from app.research_bridge.suite_requests import freeze_build

                    spec = freeze_build(binding, stage, audit, session)
                elif stage.kind == "verification":
                    from app.research_bridge.comparison_requests import freeze_verify

                    spec = freeze_verify(binding, stage, audit, session)
                else:
                    spec = freeze_repair(binding, stage, audit, session)
            resources = ToolSettings.model_validate(binding.resources)
            session.add(binding)
            session.commit()
        else:
            spec = validate_spec(binding.request)
            # WIRE-RECV:research.resources — peer: repair_requests.freeze_repair.
            # AGENT: restore every non-secret value from the frozen JSON; only
            # credentials may be injected from current runtime configuration.
            resources = ToolSettings.model_validate(binding.resources)
    if spec.implementation.code_digest != code_digest():
        raise AuditError("科研修复实现已变化，请创建新执行", code="integrity_error")
    if (
        spec.implementation.dependency_lock_digest
        != hashlib.sha256((ROOT / "system/uv.lock").read_bytes()).hexdigest()
    ):
        raise AuditError("科研依赖锁已变化，请创建新执行", code="integrity_error")
    resources = resources.model_copy(update={"AI_API_KEY": audit_settings.AI_API_KEY})

    def active(_execution_id):
        with Session(engine) as db:
            current = db.get(StageRun, UUID(str(stage_id)))
            parent = db.get(AuditRun, current.audit_id)
            if current.status == "cancelled" or parent.status == "cancelled":
                from semflow_research.public.runtime import ExecutionCancelled

                raise ExecutionCancelled("平台已请求取消，修复在安全边界停止")

    context = prepare(
        spec,
        root=research_root(),
        settings=resources,
        model=model,
        control_guard=active,
    )
    result = repair.execute(spec, context)
    with Session(engine) as session:
        binding = session.exec(
            select(ResearchBinding)
            .where(ResearchBinding.stage_id == UUID(str(stage_id)))
            .with_for_update()
        ).one()
        return project_repair(session, binding, result, root=research_root())


def reconcile_bound(stage_id):
    """Project a committed terminal native result without rerunning repair."""
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
            "completed",
            "failed",
            "cancelled",
            "interrupted",
        }:
            return None
        return project_repair(session, binding, result, root=research_root())
