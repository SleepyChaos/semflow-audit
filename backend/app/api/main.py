from fastapi import APIRouter

from app.api.routes import audits, knowledge, repairs, rules, stages, utils

api_router = APIRouter()
for router in (
    audits.router,
    stages.router,
    knowledge.router,
    rules.router,
    repairs.router,
    utils.router,
):
    api_router.include_router(router)
