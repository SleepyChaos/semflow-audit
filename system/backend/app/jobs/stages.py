import logging
from uuid import UUID

from sqlmodel import Session, select

from app.adapters.ai.provider import CompatibleModel
from app.adapters.retrieval.knowledge import index_document
from app.core.db import engine
from app.jobs.celery_app import celery_app
from app.persistence.knowledge_models import KnowledgeChunk

logger = logging.getLogger(__name__)


@celery_app.task(name="audit.stage", time_limit=0, soft_time_limit=0)
def execute_stage(stage_id: str, resume: bool = False) -> None:
    from app.runtime.stages import run_stage

    run_stage(stage_id, resume, provider_factory=CompatibleModel)


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
