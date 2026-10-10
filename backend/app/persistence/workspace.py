"""Resolve the local workspace while preserving legacy ownership foreign keys."""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert
from sqlmodel import Session, select

from app.core.config import settings
from app.models import User

WORKSPACE_ID = UUID("87801948-45be-4b30-a5c5-c804ff2ea370")
WORKSPACE_EMAIL = "workspace@semflow.local"


@dataclass(frozen=True)
class Workspace:
    id: UUID


def resolve_workspace(session: Session) -> Workspace:
    # Existing installs retain their admin's ID so audit history, rules and
    # private knowledge remain available. No credentials are read or checked.
    legacy_owner = session.exec(
        select(User.id).where(User.email == settings.FIRST_SUPERUSER)
    ).first()
    if legacy_owner is not None:
        return Workspace(legacy_owner)

    # This is an internal foreign-key anchor, not a login account. PostgreSQL's
    # conflict handling makes concurrent first requests use the same stable ID.
    anchor = User(
        id=WORKSPACE_ID,
        email=WORKSPACE_EMAIL,
        full_name="本地工作区",
        hashed_password="",
        is_active=False,
        is_superuser=False,
    )
    session.execute(
        insert(User)
        .values(**anchor.model_dump())
        .on_conflict_do_nothing(index_elements=[User.id])
    )
    session.commit()
    return Workspace(WORKSPACE_ID)
