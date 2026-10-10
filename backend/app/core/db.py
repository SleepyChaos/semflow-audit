from sqlmodel import Session, create_engine

from app.core.config import settings
from app.persistence import (  # noqa: F401
    audit_models,  # noqa: F401
    knowledge_models,
    stage_models,
)
from app.persistence.workspace import resolve_workspace

engine = create_engine(str(settings.DATABASE_URL), pool_pre_ping=True)


# make sure all SQLModel models are imported (app.models) before initializing DB
# otherwise, SQLModel might fail to initialize relationships properly
# for more details: https://github.com/fastapi/full-stack-fastapi-template/issues/28


def init_db(session: Session) -> None:
    # Tables should be created with Alembic migrations
    # But if you don't want to use migrations, create
    # the tables un-commenting the next lines
    # from sqlmodel import SQLModel

    # This works because the models are already imported and registered from app.models
    # SQLModel.metadata.create_all(engine)

    resolve_workspace(session)
