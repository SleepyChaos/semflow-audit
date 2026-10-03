from fastapi import APIRouter

from app.api.routes import (
    audits,
    items,
    knowledge,
    login,
    private,
    repairs,
    rules,
    stages,
    users,
    utils,
)
from app.core.config import settings

api_router = APIRouter()
api_router.include_router(audits.router)
api_router.include_router(login.router)
api_router.include_router(users.router)
api_router.include_router(utils.router)
api_router.include_router(items.router)


if settings.FASTAPI_ENV == "development":
    api_router.include_router(private.router)

api_router.include_router(stages.router)
api_router.include_router(knowledge.router)
api_router.include_router(rules.router)
api_router.include_router(repairs.router)
