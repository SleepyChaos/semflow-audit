from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from sqlmodel import select

from app.adapters.retrieval.embedding_identity import embedding_identity
from app.adapters.retrieval.knowledge import KnowledgeRetriever, import_knowledge
from app.api.deps import CurrentUser, SessionDep
from app.contracts.stages import KnowledgeRequest
from app.core.audit_config import audit_settings
from app.domain.audit import AuditError
from app.jobs.stages import index_knowledge
from app.persistence.knowledge_models import KnowledgeChunk

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.get("/capabilities")
def capabilities(_user: CurrentUser):
    return {
        "model_configured": bool(
            audit_settings.AI_MODEL and audit_settings.AI_BASE_URL
        ),
        "model": audit_settings.AI_MODEL or None,
        "embedding_model": audit_settings.EMBEDDING_MODEL or None,
        "retrieval": "haystack_bm25"
        if not audit_settings.EMBEDDING_MODEL
        else "haystack_bm25+optional_pgvector",
        "thinking_mode": audit_settings.AI_THINKING_MODE,
        "prompt_version": "8",
        "corpora": ["reference", "rule_example"],
        "rule_output_tokens": audit_settings.AI_RULE_TOKENS
        or audit_settings.AI_MAX_OUTPUT_TOKENS,
        "rule_generation": {
            "stable_detector_families": ["eval", "sql", "reflected_xss"],
            "source_extension_scope": "python_eval_external_call_return",
            "other_purposes_and_strategies": "experimental_free_ql_draft",
            "project_confirmation": "human_required",
        },
        "reranker": None,
        "embedding_revision": audit_settings.EMBEDDING_REVISION or None,
    }


@router.post("/", status_code=201)
def add(body: KnowledgeRequest, user: CurrentUser):
    metadata = {
        key: value
        for key, value in body.provenance.items()
        if key in {"api_version", "license", "framework", "cwe"}
        and isinstance(value, str)
        and len(value) <= 500
    }
    metadata["trust"] = "user_supplied"
    return import_knowledge(
        user.id,
        body.title,
        body.source,
        body.language,
        body.content,
        metadata,
        corpus=body.corpus,
    )


@router.get("/")
def documents(session: SessionDep, user: CurrentUser):
    rows = session.exec(
        select(KnowledgeChunk)
        .where(
            (KnowledgeChunk.owner_id == user.id) | (KnowledgeChunk.owner_id.is_(None))
        )
        .order_by(KnowledgeChunk.created_at.desc())
        .limit(1000)
    ).all()
    result = {}
    for row in rows:
        key = str(row.document_id)
        item = result.setdefault(
            key,
            {
                "document_id": key,
                "title": row.title,
                "source": row.source,
                "version": row.version,
                "language": row.language,
                "provenance": row.provenance,
                "corpus": row.corpus,
                "embedding_identity": row.embedding_identity,
                "shared": row.owner_id is None,
                "chunks": 0,
                "indexed_chunks": 0,
                "stale_indexed_chunks": 0,
                "embedding_model": row.embedding_model,
                "index_error": row.embedding_error,
            },
        )
        item["chunks"] += 1
        item["indexed_chunks"] += int(
            row.embedding is not None and row.embedding_identity == embedding_identity()
        )
        item["stale_indexed_chunks"] += int(
            row.embedding is not None and row.embedding_identity != embedding_identity()
        )
    return list(result.values())


@router.get("/search")
def search(
    user: CurrentUser,
    query: str = Query(min_length=1, max_length=5000),
    language: str = "python",
    mode: str = "auto",
    api_version: str | None = None,
    corpus: str | None = None,
):
    if language not in {"python", "javascript"}:
        raise HTTPException(422, "知识检索语言无效")
    try:
        return KnowledgeRetriever().retrieve(
            user.id, language, query, mode=mode, api_version=api_version, corpus=corpus
        )
    except AuditError as exc:
        raise HTTPException(422, str(exc))


@router.post("/{document_id}/index", status_code=202)
def index(document_id: UUID, session: SessionDep, user: CurrentUser):
    row = session.exec(
        select(KnowledgeChunk).where(
            KnowledgeChunk.document_id == document_id,
            KnowledgeChunk.owner_id == user.id,
        )
    ).first()
    if not row:
        raise HTTPException(404, "知识文档不存在")
    if not audit_settings.EMBEDDING_MODEL:
        raise HTTPException(409, "未配置向量模型；当前仍支持实际 BM25 检索")
    try:
        index_knowledge.delay(str(document_id), str(user.id))
    except Exception:
        raise HTTPException(503, "向量索引队列不可用")
    return {"status": "queued"}
