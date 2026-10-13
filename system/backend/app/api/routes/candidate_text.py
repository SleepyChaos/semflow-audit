"""Queued localization of existing candidate descriptions, with immutable inputs."""

from uuid import UUID

from fastapi import APIRouter
from sqlmodel import select

from app.api.deps import LocalWorkspace, SessionDep
from app.api.routes.audits import owned_run
from app.api.routes.stages import create_stage
from app.persistence.audit_models import AuditRun
from app.persistence.stage_models import StageRun
from app.services.candidate_localization import (
    localization_inputs,
    recover_translations,
)

router = APIRouter(tags=["stages"])


@router.post("/audits/{identifier}/localize-candidates")
def localize(identifier: UUID, session: SessionDep, workspace: LocalWorkspace):
    owned_run(identifier, session, workspace)
    audit = session.exec(
        select(AuditRun).where(AuditRun.id == identifier).with_for_update()
    ).one()
    active = session.exec(
        select(StageRun).where(
            StageRun.audit_id == identifier,
            StageRun.kind == "candidate_translation",
            StageRun.status.in_(["queued", "running"]),
        )
    ).first()
    if active:
        return active
    inputs = localization_inputs(audit, session)
    if not inputs["fields"]:
        session.commit()
        return {"status": "completed"}
    return create_stage(
        identifier,
        "candidate_translation",
        inputs,
        session,
        workspace,
        initial_result=recover_translations(identifier, inputs["fields"], session),
    )
