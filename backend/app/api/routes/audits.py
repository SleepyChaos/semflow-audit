import tempfile
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from redis import Redis
from sqlmodel import select

from app.adapters.artifacts import ArtifactStore
from app.adapters.codeql.scanner import CodeQLScanner
from app.api.deps import CurrentUser, SessionDep
from app.contracts.audit import AuditPublic
from app.core.audit_config import audit_settings
from app.domain.audit import AuditError
from app.jobs.scan import execute_scan
from app.persistence.audit_models import AuditRun
from app.services.uploads import create_run

router = APIRouter(prefix="/audits", tags=["audits"])


def owned_run(identifier: UUID, session: SessionDep, user: CurrentUser) -> AuditRun:
    run = session.get(AuditRun, identifier)
    if run is None or run.owner_id != user.id:
        raise HTTPException(404, "审计任务不存在")
    return run


def dispatch(run: AuditRun, session: SessionDep) -> None:
    try:
        execute_scan.delay(str(run.id))
    except Exception:
        run.status, run.error = "failed", "任务队列不可用，请恢复队列后重试"
        session.add(run)
        session.commit()


@router.get("/environment")
def environment(_user: CurrentUser) -> dict:
    try:
        version, error = CodeQLScanner().version(), None
    except AuditError as exc:
        version, error = None, str(exc)
    try:
        Redis.from_url(
            audit_settings.REDIS_URL, socket_connect_timeout=2, socket_timeout=2
        ).ping()
        queue = True
    except Exception:
        queue = False
    packs = (
        any(audit_settings.CODEQL_PACK_PATH.rglob("qlpack.yml"))
        if audit_settings.CODEQL_PACK_PATH.exists()
        else False
    )
    return {
        "codeql_version": version,
        "error": error,
        "query_packs_present": packs,
        "queue_available": queue,
    }


@router.get("/", response_model=list[AuditPublic])
def list_runs(
    session: SessionDep, user: CurrentUser, limit: int = Query(30, ge=1, le=100)
):
    return session.exec(
        select(AuditRun)
        .where(AuditRun.owner_id == user.id)
        .order_by(AuditRun.created_at.desc())
        .limit(limit)
    ).all()


@router.post("/", response_model=AuditPublic, status_code=201)
async def upload_run(
    session: SessionDep,
    user: CurrentUser,
    file: Annotated[UploadFile, File()],
    language: Annotated[Literal["python", "javascript"], Form()],
    project_name: Annotated[str, Form(max_length=120)] = "",
):
    if not (file.filename or "").lower().endswith(".zip"):
        raise HTTPException(422, "目前支持 ZIP 代码包")
    name = project_name.strip() or Path(file.filename or "project.zip").stem[:120]
    audit_settings.ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=audit_settings.ARTIFACT_ROOT) as temporary:
        archive = Path(temporary) / "upload.zip"
        size = 0
        with archive.open("wb") as stream:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > audit_settings.UPLOAD_LIMIT:
                    raise HTTPException(413, "代码包超过 20 MB 限制")
                stream.write(chunk)
        try:
            run = create_run(session, user.id, archive, name, language)
        except AuditError as exc:
            raise HTTPException(422, str(exc))
    dispatch(run, session)
    return run


@router.get("/{identifier}", response_model=AuditPublic)
def detail(identifier: UUID, session: SessionDep, user: CurrentUser):
    return owned_run(identifier, session, user)


@router.post("/{identifier}/retry", response_model=AuditPublic, status_code=201)
def retry(identifier: UUID, session: SessionDep, user: CurrentUser):
    previous = owned_run(identifier, session, user)
    if previous.status != "failed":
        raise HTTPException(409, "仅失败任务可创建重试执行")
    archive = ArtifactStore().directory(str(previous.source_run_id)) / "upload.zip"
    run = create_run(
        session, user.id, archive, previous.project_name, previous.language
    )
    dispatch(run, session)
    return run


@router.get("/{identifier}/logs")
def logs(identifier: UUID, session: SessionDep, user: CurrentUser):
    owned_run(identifier, session, user)
    return {"text": ArtifactStore().log_tail(str(identifier))}


@router.get("/{identifier}/source")
def source(
    identifier: UUID,
    session: SessionDep,
    user: CurrentUser,
    file: str,
    line: int = Query(1, ge=1),
):
    run = owned_run(identifier, session, user)
    root = ArtifactStore().source(str(run.source_run_id)).resolve()
    target = (root / file).resolve()
    if not target.is_relative_to(root) or not target.is_file():
        raise HTTPException(404, "源码位置不在本次快照中")
    if target.stat().st_size > 1024 * 1024:
        raise HTTPException(413, "该源码文件过大，暂不提供在线预览")
    try:
        lines = target.read_text().splitlines()
    except UnicodeError:
        raise HTTPException(422, "源码不是 UTF-8 文本")
    start = max(0, line - 8)
    return {
        "file": target.relative_to(root).as_posix(),
        "start_line": start + 1,
        "lines": lines[start : line + 12],
    }


@router.get("/{identifier}/sarif")
def download_sarif(identifier: UUID, session: SessionDep, user: CurrentUser):
    run = owned_run(identifier, session, user)
    path = ArtifactStore().directory(str(identifier)) / "results.sarif"
    if run.status != "completed" or not path.is_file():
        raise HTTPException(409, "该任务尚无成功完成的 SARIF")
    return FileResponse(
        path, filename=f"{identifier}.sarif", media_type="application/json"
    )
