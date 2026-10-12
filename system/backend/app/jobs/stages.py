import logging
from uuid import UUID

from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.types import Command
from sqlmodel import Session, select

from app.adapters.ai.provider import CompatibleModel
from app.adapters.retrieval.knowledge import index_document
from app.core.config import settings
from app.core.db import engine
from app.jobs.celery_app import celery_app
from app.persistence.knowledge_models import KnowledgeChunk
from app.persistence.stage_repository import StageCancelled, StageRepository
from app.services.repair import RepairService
from app.services.report_generation import ReportService
from app.services.review import ReviewService
from app.services.rules import RuleService
from app.services.scouting import ScoutService
from app.workflows.repair import build_repair_graph
from app.workflows.report import build_report_graph
from app.workflows.review import build_review_graph
from app.workflows.rules import build_rule_graph
from app.workflows.scouting import build_scout_graph

logger = logging.getLogger(__name__)


@celery_app.task(name="audit.stage")
def execute_stage(stage_id: str, resume: bool = False) -> None:
    repository = StageRepository()
    if not repository.claim(stage_id):
        return
    provider = None
    try:
        stage = repository.get(stage_id)
        if stage.kind == "verification":
            from app.services.repair_comparison import ComparisonService

            ComparisonService(stage_id).run()
            return
        provider = CompatibleModel()
        if hasattr(provider, "bind_stage"):
            provider.bind_stage(stage_id, stage.prompt_version)
        if stage.kind == "verification_suite":
            from app.services.verification_suites import SuiteService

            SuiteService(stage_id, provider).run()
            return
        services = {
            "review": (ReviewService, build_review_graph),
            "repair": (RepairService, build_repair_graph),
            "rule": (RuleService, build_rule_graph),
            "scout": (ScoutService, build_scout_graph),
            "report": (ReportService, build_report_graph),
        }
        service_type, graph_builder = services[stage.kind]
        service = service_type(stage_id, provider)
        url = str(settings.DATABASE_URL).replace(
            "postgresql+psycopg://", "postgresql://", 1
        )
        with PostgresSaver.from_conn_string(url) as saver:
            graph = graph_builder(service, saver)
            result = graph.invoke(
                Command(resume={"approved": True})
                if resume
                else {"stage_id": stage_id},
                config={"configurable": {"thread_id": stage_id}, "recursion_limit": 60},
            )
            if result.get("__interrupt__"):
                repository.update(
                    stage_id,
                    status="awaiting_confirmation",
                    phase="awaiting_fixture_approval",
                )
    except StageCancelled:
        logger.info("Stage cancelled: %s", stage_id)
    except Exception as exc:
        logger.exception("Stage failed: %s", stage_id)
        try:
            repository.update(
                stage_id,
                status="failed",
                error=str(exc)[:1000],
                result={
                    **repository.get(stage_id).result,
                    "failure": {"code": getattr(exc, "code", "internal_error")},
                },
                usage=provider.usage if provider else {},
            )
        except StageCancelled:
            pass


@celery_app.task(name="audit.knowledge_index")
def index_knowledge(document_id: str, owner_id: str) -> None:
    try:
        index_document(UUID(document_id), UUID(owner_id))
    except Exception as exc:
        logger.exception("Knowledge index failed: %s", document_id)
        with Session(engine) as session:
            rows = session.exec(
                select(KnowledgeChunk).where(
                    KnowledgeChunk.document_id == UUID(document_id),
                    KnowledgeChunk.owner_id == UUID(owner_id),
                )
            ).all()
            for row in rows:
                row.embedding_error = str(exc)[:1000]
                session.add(row)
            session.commit()
