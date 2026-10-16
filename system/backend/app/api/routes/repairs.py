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
    from app.services.repair_comparison import acceptance_ready, comparison_state

    result = []
    from app.services.repair_localization import localized_repair, translation_jobs

    translations = translation_jobs(audit_id, session)
    for row in rows:
        comparison = comparison_state(session, row)
        result.append(
            {
                **localized_repair(row.model_dump(mode="json"), translations),
                "comparison": comparison,
                "acceptance_ready": acceptance_ready(row, comparison),
                "validation_summary": explain_validation(row.validation, comparison),
            }
        )
    return result


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
    from app.services.repair_comparison import acceptance_ready, comparison_state

    comparison = comparison_state(session, record)
    if record.status == "accepted":
        raise HTTPException(409, "该补丁已接受，验收记录保留")
    if not acceptance_ready(record, comparison):
        raise HTTPException(
            409,
            "请先完成漏洞复现、补丁后阻断、正常功能保持和所选检查；语法通过不能代替修复验收",
        )
    if not body.test_reviewed or str(body.comparison_stage_id) != comparison.get(
        "stage_id"
    ):
        raise HTTPException(409, "请审阅当前测试断言、前后结果与补丁，再确认接受")
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
    from app.persistence.stage_models import StageRun

    session.add(
        StageRun(
            audit_id=record.audit_id,
            kind="verification_acceptance",
            status="completed",
            phase="patch_accepted",
            result={
                "repair_id": str(record.id),
                "comparison_stage_id": comparison["stage_id"],
                "receipt_hash": comparison["receipt_hash"],
                "suite_hash": comparison["identity"]["suite_hash"],
                "actor_id": str(workspace.id),
                "reason": body.reason,
                "test_reviewed": True,
                "scope": comparison["meaning"],
            },
        )
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
