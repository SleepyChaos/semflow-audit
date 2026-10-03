from uuid import UUID

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
from sqlmodel import select

from app.adapters.artifacts import ArtifactStore
from app.api.deps import CurrentUser, SessionDep
from app.api.routes.audits import owned_run
from app.contracts.stages import RepairAcceptance
from app.persistence.stage_models import Candidate, RepairRecord
from app.services.reports import build_report, markdown_report

router = APIRouter(tags=["repairs", "reports"])


@router.get("/audits/{audit_id}/repairs")
def repairs(audit_id: UUID, session: SessionDep, user: CurrentUser):
    owned_run(audit_id, session, user)
    return session.exec(
        select(RepairRecord).where(RepairRecord.audit_id == audit_id)
    ).all()


def owned_repair(identifier: UUID, session: SessionDep, user: CurrentUser):
    record = session.get(RepairRecord, identifier)
    if record is None:
        raise HTTPException(404, "修复记录不存在")
    owned_run(record.audit_id, session, user)
    return record


@router.get("/repairs/{identifier}/diff")
def diff(identifier: UUID, session: SessionDep, user: CurrentUser):
    record = owned_repair(identifier, session, user)
    path = ArtifactStore().directory(str(record.stage_id)) / "repair.diff"
    if not path.is_file():
        raise HTTPException(409, "该修复尚未生成 Diff")
    return FileResponse(path, filename=f"{identifier}.diff", media_type="text/plain")


@router.post("/repairs/{identifier}/accept")
def accept(
    identifier: UUID, body: RepairAcceptance, session: SessionDep, user: CurrentUser
):
    record = owned_repair(identifier, session, user)
    if record.status != "checks_passed":
        raise HTTPException(409, "请先完成所选测试和目标复扫；证据不足的补丁保持草稿")
    candidates = [
        session.get(Candidate, UUID(identifier)) for identifier in record.candidate_ids
    ]
    if any(row is None or row.status != "confirmed" for row in candidates):
        raise HTTPException(409, "修复目标确认状态已变化，请重新评估补丁")
    record.status, record.accepted_by, record.acceptance_reason = (
        "accepted",
        user.id,
        body.reason,
    )
    session.add(record)
    session.commit()
    return {
        "status": "accepted",
        "original_snapshot_unchanged": True,
        "delivery": "download_diff_for_manual_application",
    }


@router.get("/audits/{audit_id}/report")
def report(audit_id: UUID, session: SessionDep, user: CurrentUser):
    return build_report(session, owned_run(audit_id, session, user))


@router.get("/audits/{audit_id}/report.md", response_class=PlainTextResponse)
def report_markdown(audit_id: UUID, session: SessionDep, user: CurrentUser):
    document = build_report(session, owned_run(audit_id, session, user))
    return PlainTextResponse(
        markdown_report(document),
        headers={"Content-Disposition": f'attachment; filename="{audit_id}-report.md"'},
    )
