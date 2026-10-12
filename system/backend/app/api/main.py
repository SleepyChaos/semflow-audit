from fastapi import APIRouter

from app.api.routes import (
    audits,
    knowledge,
    repairs,
    rules,
    stages,
    utils,
    verification,
)

api_router = APIRouter()
for router in (
    audits.router,
    stages.router,
    knowledge.router,
    rules.router,
    repairs.router,
    verification.router,
    utils.router,
):
    api_router.include_router(router)
