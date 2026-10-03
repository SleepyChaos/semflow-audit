from uuid import UUID

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy import update
from sqlmodel import select

from app.api.deps import CurrentUser, SessionDep
from app.api.routes.stages import dispatch_stage
from app.contracts.stages import FixtureApproval
from app.domain.audit import AuditError
from app.models import get_datetime_utc
from app.persistence.knowledge_models import RuleVersion
from app.persistence.stage_models import StageRun
from app.services.rules import publish_rule

router = APIRouter(prefix="/rules", tags=["rules"])


def owned_rule(identifier: UUID, session: SessionDep, user: CurrentUser) -> RuleVersion:
    rule = session.get(RuleVersion, identifier)
    if rule is None or rule.owner_id != user.id:
        raise HTTPException(404, "规则版本不存在")
    return rule


@router.get("/")
def rules(
    session: SessionDep,
    user: CurrentUser,
    language: str | None = None,
    published: bool = False,
):
    query = select(RuleVersion).where(RuleVersion.owner_id == user.id)
    if language:
        query = query.where(RuleVersion.language == language)
    if published:
        query = query.where(RuleVersion.status == "published")
    return session.exec(query.order_by(RuleVersion.created_at.desc()).limit(100)).all()


@router.get("/{identifier}")
def detail(identifier: UUID, session: SessionDep, user: CurrentUser):
    return owned_rule(identifier, session, user)


@router.get("/{identifier}/query", response_class=PlainTextResponse)
def query_file(identifier: UUID, session: SessionDep, user: CurrentUser):
    rule = owned_rule(identifier, session, user)
    return PlainTextResponse(
        rule.query,
        headers={"Content-Disposition": f'attachment; filename="{identifier}.ql"'},
    )


@router.post("/{identifier}/approve-fixtures")
def approve(
    identifier: UUID, body: FixtureApproval, session: SessionDep, user: CurrentUser
):
    rule = owned_rule(identifier, session, user)
    stage = session.get(StageRun, rule.stage_id)
    if rule.status != "draft" or stage.status != "awaiting_confirmation":
        raise HTTPException(409, "当前规则不处于等待样本确认状态")
    result = session.execute(
        update(StageRun)
        .where(StageRun.id == stage.id, StageRun.status == "awaiting_confirmation")
        .values(status="queued", updated_at=get_datetime_utc())
    )
    if result.rowcount != 1:
        session.rollback()
        raise HTTPException(409, "样本确认已被其他请求处理")
    rule.fixtures_approved, rule.fixture_approval_reason = True, body.reason
    session.add(rule)
    session.commit()
    session.refresh(stage)
    dispatch_stage(stage, session, resume=True)
    return stage


@router.post("/{identifier}/publish")
def publish(identifier: UUID, session: SessionDep, user: CurrentUser):
    rule = owned_rule(identifier, session, user)
    try:
        publish_rule(rule)
    except AuditError as exc:
        raise HTTPException(409, str(exc))
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return rule


@router.post("/{identifier}/retire")
def retire(identifier: UUID, session: SessionDep, user: CurrentUser):
    rule = owned_rule(identifier, session, user)
    if rule.status != "published":
        raise HTTPException(409, "仅已发布规则可以停用")
    rule.status = "retired"
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return rule
