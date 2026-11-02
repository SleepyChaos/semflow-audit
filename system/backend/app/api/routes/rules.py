from uuid import UUID

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse
from sqlmodel import select

from app.api.deps import LocalWorkspace, SessionDep
from app.api.routes.stages import dispatch_stage
from app.contracts.stages import FixtureApproval, ProjectMatchConfirmation
from app.domain.audit import AuditError
from app.persistence.knowledge_models import RuleVersion
from app.services.rules import publish_rule

router = APIRouter(prefix="/rules", tags=["rules"])


def owned_rule(
    identifier: UUID, session: SessionDep, workspace: LocalWorkspace
) -> RuleVersion:
    rule = session.get(RuleVersion, identifier)
    if rule is None or rule.owner_id != workspace.id:
        raise HTTPException(404, "规则版本不存在")
    return rule


@router.get("/holdouts")
def holdouts(_workspace: LocalWorkspace):
    from app.services.rule_holdouts import catalog

    return catalog()


@router.get("/")
def rules(
    session: SessionDep,
    workspace: LocalWorkspace,
    language: str | None = None,
    published: bool = False,
):
    query = select(RuleVersion).where(RuleVersion.owner_id == workspace.id)
    if language:
        query = query.where(RuleVersion.language == language)
    if published:
        query = query.where(RuleVersion.status == "published")
    return session.exec(query.order_by(RuleVersion.created_at.desc()).limit(100)).all()


@router.get("/{identifier}")
def detail(identifier: UUID, session: SessionDep, workspace: LocalWorkspace):
    return owned_rule(identifier, session, workspace)


@router.get("/{identifier}/query", response_class=PlainTextResponse)
def query_file(identifier: UUID, session: SessionDep, workspace: LocalWorkspace):
    rule = owned_rule(identifier, session, workspace)
    return PlainTextResponse(
        rule.query,
        headers={"Content-Disposition": f'attachment; filename="{identifier}.ql"'},
    )


@router.post("/{identifier}/approve-fixtures")
def approve(
    identifier: UUID,
    body: FixtureApproval,
    session: SessionDep,
    workspace: LocalWorkspace,
):
    rule = owned_rule(identifier, session, workspace)
    from app.services.stage_actions import approve_stage

    try:
        stage = approve_stage(session, rule.stage_id, workspace.id, body.reason)
    except AuditError as exc:
        raise HTTPException(409, str(exc)) from exc
    dispatch_stage(stage, session, resume=True)
    return stage


@router.post("/{identifier}/confirm-project-match")
def confirm_project(
    identifier: UUID,
    body: ProjectMatchConfirmation,
    session: SessionDep,
    workspace: LocalWorkspace,
):
    from app.services.rule_project_validation import confirm_project_match

    rule = owned_rule(identifier, session, workspace)
    if rule.status == "published":
        raise HTTPException(409, "已发布规则不可改变验收记录")
    try:
        confirm_project_match(
            rule,
            body.finding_id,
            workspace.id,
            body.reason,
            body.baseline_exclusion_reason,
        )
    except AuditError as exc:
        raise HTTPException(409, str(exc)) from exc
    if (
        rule.fixtures_approved
        and rule.validation.get("status") == "passed"
        and rule.validation.get("independent_holdout", {}).get("status") == "passed"
    ):
        rule.status = "validated"
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return rule


@router.post("/{identifier}/publish")
def publish(identifier: UUID, session: SessionDep, workspace: LocalWorkspace):
    rule = owned_rule(identifier, session, workspace)
    try:
        publish_rule(rule)
    except AuditError as exc:
        raise HTTPException(409, str(exc))
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return rule


@router.post("/{identifier}/retire")
def retire(identifier: UUID, session: SessionDep, workspace: LocalWorkspace):
    rule = owned_rule(identifier, session, workspace)
    if rule.status != "published":
        raise HTTPException(409, "仅已发布规则可以停用")
    rule.status = "retired"
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return rule
