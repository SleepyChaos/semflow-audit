from collections.abc import Generator
from typing import Annotated

from fastapi import Depends
from sqlmodel import Session

from app.core.db import engine
from app.persistence.workspace import Workspace, resolve_workspace


def get_db() -> Generator[Session]:
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_db)]


def get_workspace(session: SessionDep) -> Workspace:
    return resolve_workspace(session)


LocalWorkspace = Annotated[Workspace, Depends(get_workspace)]
