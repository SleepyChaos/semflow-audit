"""Owned project tests and immutable repair comparison jobs."""

from uuid import UUID

from fastapi import APIRouter, HTTPException
from sqlmodel import select

from app.api.deps import LocalWorkspace, SessionDep
from app.api.routes.audits import owned_run
from app.api.routes.repairs import owned_repair
from app.api.routes.stages import create_stage
from app.contracts.verification import SuiteGeneration, SuiteImport, VerificationRequest
from app.core.audit_config import audit_settings
from app.domain.audit import AuditError
from app.persistence.stage_models import StageRun
from app.services.repair_comparison import comparison_materials
from app.services.verification_suites import candidate_scope, freeze_suite

router = APIRouter(tags=["repair-verification"])


@router.get("/audits/{audit_id}/verification-environment")
def verification_environment(
    audit_id: UUID, session: SessionDep, workspace: LocalWorkspace
):
    from app.adapters.repair.verification_runner import resolve_image
    from app.services.verification_suites import image_default

    audit = owned_run(audit_id, session, workspace)
    try:
        image_id = resolve_image(image_default(audit.language))
    except AuditError as exc:
        return {"ready": False, "error": str(exc)}
    return {"ready": True, "image_id": image_id, "error": None}


@router.get("/audits/{audit_id}/verification-suites")
def suites(audit_id: UUID, session: SessionDep, workspace: LocalWorkspace):
    owned_run(audit_id, session, workspace)
    rows = session.exec(
        select(StageRun)
        .where(
            StageRun.audit_id == audit_id,
            StageRun.kind == "verification_suite",
            StageRun.status == "completed",
        )
        .order_by(StageRun.created_at.desc())
    ).all()
    return [{"id": str(row.id), **row.result} for row in rows]


@router.post("/audits/{audit_id}/verification-suites/generate", status_code=201)
def generate_suite(
    audit_id: UUID,
    body: SuiteGeneration,
    session: SessionDep,
    workspace: LocalWorkspace,
):
    owned_run(audit_id, session, workspace)
    if not audit_settings.AI_MODEL or not audit_settings.AI_BASE_URL:
        raise HTTPException(409, "未配置模型，可导入已有测试集")
    try:
        candidate_scope(audit_id, body.candidate_ids)
    except AuditError as exc:
        raise HTTPException(409, str(exc)) from exc
    return create_stage(
        audit_id, "verification_suite", body.model_dump(mode="json"), session, workspace
    )


@router.post("/audits/{audit_id}/verification-suites/import", status_code=201)
def import_suite(
    audit_id: UUID, body: SuiteImport, session: SessionDep, workspace: LocalWorkspace
):
    audit = owned_run(audit_id, session, workspace)
    if audit.status not in {"completed", "failed"}:
        raise HTTPException(409, "请先完成审计")
    stage = StageRun(
        audit_id=audit_id,
        kind="verification_suite",
        status="completed",
        phase="verification_suite_ready",
    )
    try:
        result = freeze_suite(stage, body.suite, body.image, "imported")
    except (AuditError, ValueError, OSError, SyntaxError) as exc:
        raise HTTPException(422, str(exc)) from exc
    stage.result = result
    session.add(stage)
    session.commit()
    session.refresh(stage)
    return stage


@router.post("/repairs/{identifier}/verify", status_code=201)
def verify_repair(
    identifier: UUID,
    body: VerificationRequest,
    session: SessionDep,
    workspace: LocalWorkspace,
):
    record = owned_repair(identifier, session, workspace)
    source_stage = session.get(StageRun, record.stage_id)
    if source_stage.status != "completed" or record.status == "accepted":
        raise HTTPException(409, "请等待补丁生成结束；已接受记录保留原验收")
    try:
        identity = comparison_materials(record, body.suite_id)[0]
    except (AuditError, OSError, ValueError, KeyError) as exc:
        raise HTTPException(409, str(exc)) from exc
    active = session.exec(
        select(StageRun).where(
            StageRun.audit_id == record.audit_id,
            StageRun.kind == "verification",
            StageRun.status.in_(["queued", "running"]),
        )
    ).all()
    for stage in active:
        if stage.inputs.get("identity") == identity:
            return stage
    return create_stage(
        record.audit_id,
        "verification",
        {
            "repair_id": str(record.id),
            "suite_id": str(body.suite_id),
            "identity": identity,
        },
        session,
        workspace,
    )
