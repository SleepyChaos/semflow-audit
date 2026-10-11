from uuid import UUID

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
from sqlmodel import select

from app.adapters.artifacts import ArtifactStore
from app.api.deps import LocalWorkspace, SessionDep
from app.api.routes.audits import owned_run
from app.api.routes.stages import create_stage
from app.contracts.stages import RepairAcceptance, StrictModel
from app.core.audit_config import audit_settings
from app.domain.audit import AuditError
from app.persistence.stage_models import Candidate, RepairRecord
from app.services.reports import build_report, markdown_report

router = APIRouter(tags=["repairs", "reports"])


@router.get("/audits/{audit_id}/repairs")
def repairs(audit_id: UUID, session: SessionDep, workspace: LocalWorkspace):
    owned_run(audit_id, session, workspace)
    from app.services.result_explanations import explain_validation

    rows = session.exec(
        select(RepairRecord).where(RepairRecord.audit_id == audit_id)
    ).all()
    return [
        {
            **row.model_dump(mode="json"),
            "validation_summary": explain_validation(row.validation),
        }
        for row in rows
    ]


def owned_repair(identifier: UUID, session: SessionDep, workspace: LocalWorkspace):
    record = session.get(RepairRecord, identifier)
    if record is None:
        raise HTTPException(404, "修复记录不存在")
    owned_run(record.audit_id, session, workspace)
    return record


@router.get("/repairs/{identifier}/diff")
def diff(identifier: UUID, session: SessionDep, workspace: LocalWorkspace):
    record = owned_repair(identifier, session, workspace)
    path = ArtifactStore().directory(str(record.stage_id)) / "repair.diff"
    if not path.is_file():
        raise HTTPException(409, "该修复尚未生成 Diff")
    return FileResponse(path, filename=f"{identifier}.diff", media_type="text/plain")


@router.post("/repairs/{identifier}/accept")
def accept(
    identifier: UUID,
    body: RepairAcceptance,
    session: SessionDep,
    workspace: LocalWorkspace,
):
    record = owned_repair(identifier, session, workspace)
    if record.status != "checks_passed":
        raise HTTPException(409, "请先完成所选测试和目标复扫；证据不足的补丁保持草稿")
    candidates = [
        session.get(Candidate, UUID(identifier)) for identifier in record.candidate_ids
    ]
    if any(row is None or row.status != "confirmed" for row in candidates):
        raise HTTPException(409, "修复目标确认状态已变化，请重新评估补丁")
    from app.services.repair_integrity import verify_acceptance

    try:
        verify_acceptance(record, owned_run(record.audit_id, session, workspace))
    except (AuditError, OSError, KeyError, ValueError) as exc:
        raise HTTPException(409, "补丁或验证产物失效，请重新验证") from exc
    record.status, record.accepted_by, record.acceptance_reason = (
        "accepted",
        workspace.id,
        body.reason,
    )
    session.add(record)
    session.commit()
    return {
        "status": "accepted",
        "original_snapshot_unchanged": True,
        "delivery": "download_diff_for_manual_application",
    }


class ReportRequest(StrictModel):
    force: bool = False


@router.post("/audits/{audit_id}/report-analysis")
def generate_report(
    audit_id: UUID, body: ReportRequest, session: SessionDep, workspace: LocalWorkspace
):
    from app.persistence.stage_models import StageRun
    from app.services.report_generation import source_fingerprint

    if not audit_settings.AI_MODEL or not audit_settings.AI_BASE_URL:
        raise HTTPException(409, "请先配置模型服务，中文 AI 报告不能使用模板代替")
    document = build_report(session, owned_run(audit_id, session, workspace))
    active = session.exec(
        select(StageRun).where(
            StageRun.audit_id == audit_id,
            StageRun.kind == "report",
            StageRun.status.in_(["queued", "running"]),
        )
    ).first()
    if active:
        return active
    if document["ai_report"]["status"] == "ready" and not body.force:
        return session.get(StageRun, UUID(document["ai_report"]["stage_id"]))
    return create_stage(
        audit_id,
        "report",
        {"source_fingerprint": source_fingerprint(document)},
        session,
        workspace,
    )


@router.get("/audits/{audit_id}/report")
def report(audit_id: UUID, session: SessionDep, workspace: LocalWorkspace):
    return build_report(session, owned_run(audit_id, session, workspace))


@router.get("/audits/{audit_id}/report.md", response_class=PlainTextResponse)
def report_markdown(audit_id: UUID, session: SessionDep, workspace: LocalWorkspace):
    document = build_report(session, owned_run(audit_id, session, workspace))
    if document["ai_report"]["status"] != "ready":
        raise HTTPException(409, "AI 中文报告尚未生成或结果已变化，请先生成或更新报告")
    return PlainTextResponse(
        markdown_report(document),
        headers={"Content-Disposition": f'attachment; filename="{audit_id}-report.md"'},
    )
