from fastapi import APIRouter

from app.api.routes import (
    audits,
    candidate_sources,
    candidate_text,
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
    candidate_sources.router,
    candidate_text.router,
    knowledge.router,
    rules.router,
    repairs.router,
    verification.router,
    utils.router,
):
    api_router.include_router(router)
