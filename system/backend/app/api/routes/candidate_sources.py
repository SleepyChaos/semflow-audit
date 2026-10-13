"""Read and supplement evidence attached to one owned candidate."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import Field
from sqlmodel import select

from app.api.deps import LocalWorkspace, SessionDep
from app.api.routes.audits import owned_run
from app.contracts.stages import StrictModel
from app.domain.audit import AuditError
from app.persistence.stage_models import Candidate, Evidence

router = APIRouter(tags=["stages"])


class ClassificationRequest(StrictModel):
    status: Literal["confirmed", "excluded", "insufficient"]


@router.post("/candidates/{identifier}/classification", status_code=201)
def classify(
    identifier: UUID,
    body: ClassificationRequest,
    session: SessionDep,
    workspace: LocalWorkspace,
):
    candidate, _ = owned_candidate(identifier, session, workspace)
    from app.services.candidate_classification import change_classification

    try:
        return change_classification(candidate, body.status, workspace.id, session)
    except AuditError as exc:
        raise HTTPException(409, str(exc)) from exc


def owned_candidate(identifier, session, workspace):
    candidate = session.get(Candidate, identifier)
    if candidate is None:
        raise HTTPException(404, "候选不存在")
    audit = owned_run(candidate.audit_id, session, workspace)
    return candidate, audit


@router.get("/candidates/{identifier}/evidence")
def evidence(identifier: UUID, session: SessionDep, workspace: LocalWorkspace):
    candidate, audit = owned_candidate(identifier, session, workspace)
    return session.exec(
        select(Evidence)
        .where(
            Evidence.audit_id == audit.id,
            Evidence.id.in_([UUID(value) for value in candidate.evidence_ids]),
            Evidence.snapshot_hash == audit.snapshot_hash,
        )
        .order_by(Evidence.created_at)
    ).all()


class SourceRequest(StrictModel):
    file: str = Field(min_length=1, max_length=500)
    line: int = Field(default=1, ge=1)


@router.post("/candidates/{identifier}/source", status_code=201)
def add_source(
    identifier: UUID,
    body: SourceRequest,
    session: SessionDep,
    workspace: LocalWorkspace,
):
    candidate, _ = owned_candidate(identifier, session, workspace)
    from app.services.candidate_sources import supplement_source

    try:
        return supplement_source(candidate, body.file, body.line, session)
    except (AuditError, OSError, ValueError) as exc:
        raise HTTPException(409, str(exc)) from exc
