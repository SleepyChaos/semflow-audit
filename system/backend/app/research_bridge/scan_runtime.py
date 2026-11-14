"""Platform scan task -> explicit frozen request -> same discovery public API."""

from uuid import UUID

from semflow_contracts.runs import validate_spec
from semflow_research.public import discovery
from semflow_research.public.implementation import code_digest
from semflow_research.public.runs import inspect
from semflow_research.public.runtime import ExecutionCancelled, ToolSettings, prepare
from sqlmodel import Session, select

from app.contracts.scouting import ScoutRequest
from app.core.audit_config import audit_settings
from app.core.db import engine
from app.persistence.audit_models import AuditRun
from app.persistence.stage_models import StageRun
from app.research_bridge.models import ResearchAuditBinding, ResearchBinding
from app.research_bridge.requests import research_root
from app.research_bridge.scan_projection import project_scan
from app.research_bridge.scan_requests import freeze_scan


def binding_for_audit(audit_id):
    with Session(engine) as session:
        return session.exec(
            select(ResearchAuditBinding).where(
                ResearchAuditBinding.audit_id == UUID(str(audit_id))
            )
        ).first()


def execute_scan(audit_id, *, model=None, replay_only=False):
    with Session(engine) as session:
        binding = session.exec(
            select(ResearchAuditBinding)
            .where(ResearchAuditBinding.audit_id == UUID(str(audit_id)))
            .with_for_update()
        ).one()
        audit = session.get(AuditRun, binding.audit_id)
        if binding.manifest is not None:
            return audit
        if replay_only:
            result = (
                inspect(binding.execution_id, root=research_root())
                if binding.request
                else None
            )
            if result is not None and result.execution_status in {
                "completed",
                "failed",
                "cancelled",
                "interrupted",
            }:
                return project_scan(session, binding, audit, result)
            return None
        if not binding.request:
            spec, resources = freeze_scan(binding, audit)
            if spec.operation == "discover":
                stage = StageRun(
                    audit_id=audit.id,
                    kind="scout",
                    status="running",
                    phase="scout_windows",
                    prompt_version="7",
                    inputs=ScoutRequest().model_dump(mode="json"),
                    model_config_snapshot=binding.policy,
                )
                session.add(stage)
                binding.scout_stage_id = stage.id
                session.add(
                    ResearchBinding(
                        execution_id=discovery.child_execution_id(
                            spec.execution_id, "scout"
                        ),
                        stage_id=stage.id,
                    )
                )
            session.add(binding)
            session.commit()
        else:
            spec = validate_spec(binding.request)
            resources = ToolSettings.model_validate(binding.resources).model_copy(
                update={"AI_API_KEY": audit_settings.AI_API_KEY}
            )
        scout_stage_id = binding.scout_stage_id
    if code_digest() != spec.implementation.code_digest:
        raise ValueError("Bound scan implementation changed; create a new execution")

    def active(execution_id):
        with Session(engine) as db:
            audit = db.get(AuditRun, UUID(str(audit_id)))
            scout = db.get(StageRun, scout_stage_id) if scout_stage_id else None
            if audit.status == "cancelled" or (
                scout
                and execution_id
                == discovery.child_execution_id(spec.execution_id, "scout")
                and scout.status == "cancelled"
            ):
                raise ExecutionCancelled("平台已请求取消，科研分支在安全边界停止")

    context = prepare(
        spec,
        root=research_root(),
        settings=resources,
        model=model,
        control_guard=active,
    )
    result = discovery.execute(spec, context)
    with Session(engine) as session:
        binding = session.exec(
            select(ResearchAuditBinding)
            .where(ResearchAuditBinding.audit_id == UUID(str(audit_id)))
            .with_for_update()
        ).one()
        return project_scan(
            session, binding, session.get(AuditRun, binding.audit_id), result
        )
