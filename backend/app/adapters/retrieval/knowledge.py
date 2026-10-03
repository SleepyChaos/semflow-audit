"""Persistent, versioned knowledge with Haystack BM25 and optional pgvector fusion."""

import hashlib
import math
import os
from uuid import UUID, uuid4

os.environ.setdefault("HAYSTACK_TELEMETRY_ENABLED", "False")
from haystack import Document, Pipeline
from haystack.components.retrievers.in_memory import InMemoryBM25Retriever
from haystack.document_stores.in_memory import InMemoryDocumentStore
from sqlmodel import Session, select

from app.adapters.ai.provider import CompatibleModel
from app.core.audit_config import audit_settings
from app.core.db import engine
from app.domain.audit import AuditError
from app.persistence.knowledge_models import KnowledgeChunk


def import_knowledge(
    owner_id: UUID | None, title: str, source: str, language: str, content: str
) -> dict:
    digest = hashlib.sha256(content.encode()).hexdigest()
    document_id = uuid4()
    rows = []
    # Stable version hash; overlapping chunks retain their original exact text.
    for position, start in enumerate(range(0, len(content), 1600)):
        text = content[start : start + 1800]
        rows.append(
            KnowledgeChunk(
                owner_id=owner_id,
                document_id=document_id,
                version=digest,
                title=title,
                source=source,
                language=language,
                position=position,
                content=text,
                digest=hashlib.sha256(text.encode()).hexdigest(),
            )
        )
    with Session(engine) as session:
        session.add_all(rows)
        session.commit()
    return {"document_id": str(document_id), "version": digest, "chunks": len(rows)}


def index_document(document_id: UUID, owner_id: UUID) -> None:
    with Session(engine) as session:
        rows = session.exec(
            select(KnowledgeChunk)
            .where(
                KnowledgeChunk.document_id == document_id,
                KnowledgeChunk.owner_id == owner_id,
            )
            .order_by(KnowledgeChunk.position)
        ).all()
        if not rows:
            raise AuditError("知识文档不存在")
        model = CompatibleModel()
        for start in range(0, len(rows), 8):
            batch = rows[start : start + 8]
            embeddings = model.embed([row.content for row in batch])
            if len(embeddings) != len(batch):
                raise AuditError("向量服务返回数量不匹配")
            for row, vector in zip(batch, embeddings, strict=True):
                if (
                    not vector
                    or len(vector) > 4096
                    or not all(math.isfinite(value) for value in vector)
                    or not any(vector)
                ):
                    raise AuditError("向量维度无效")
                row.embedding = vector
                row.embedding_model = audit_settings.EMBEDDING_MODEL
                row.embedding_error = None
                session.add(row)
        session.commit()


class KnowledgeRetriever:
    def retrieve(
        self, owner_id: UUID, language: str, query: str, top_k: int = 6
    ) -> list[dict]:
        if not query or len(query) > 5000:
            raise AuditError("知识检索请求无效")
        with Session(engine) as session:
            condition = (KnowledgeChunk.owner_id == owner_id) | (
                KnowledgeChunk.owner_id.is_(None)
            )
            rows = session.exec(
                select(KnowledgeChunk)
                .where(condition, KnowledgeChunk.language.in_([language, "any"]))
                .order_by(KnowledgeChunk.created_at.desc())
                .limit(1000)
            ).all()
            if not rows:
                return []
            store = InMemoryDocumentStore(
                bm25_tokenization_regex=r"(?u)[\u4e00-\u9fff]|[a-zA-Z0-9_]+"
            )
            store.write_documents(
                [Document(id=str(row.id), content=row.content) for row in rows]
            )
            pipeline = Pipeline()
            pipeline.add_component(
                "retrieve", InMemoryBM25Retriever(document_store=store, top_k=top_k * 2)
            )
            lexical = pipeline.run({"retrieve": {"query": query}})["retrieve"][
                "documents"
            ]
            ranked = {}
            methods = ["haystack_bm25"]
            for rank, document in enumerate(lexical):
                if (document.score or 0) > 0:
                    ranked[document.id] = 1 / (60 + rank)
            if audit_settings.EMBEDDING_MODEL and any(
                row.embedding_model == audit_settings.EMBEDDING_MODEL for row in rows
            ):
                vector = CompatibleModel().embed([query])[0]
                if any(
                    len(row.embedding) != len(vector)
                    for row in rows
                    if row.embedding_model == audit_settings.EMBEDDING_MODEL
                    and row.embedding is not None
                ):
                    raise AuditError("向量模型维度变化，请重新索引知识库")
                semantic = session.exec(
                    select(KnowledgeChunk)
                    .where(
                        condition,
                        KnowledgeChunk.language.in_([language, "any"]),
                        KnowledgeChunk.embedding_model
                        == audit_settings.EMBEDDING_MODEL,
                        KnowledgeChunk.embedding.is_not(None),
                    )
                    .order_by(KnowledgeChunk.embedding.cosine_distance(vector))
                    .limit(top_k * 2)
                ).all()
                for rank, row in enumerate(semantic):
                    ranked[str(row.id)] = ranked.get(str(row.id), 0) + 1 / (60 + rank)
                methods.append("pgvector_cosine_rrf")
                rows = list({row.id: row for row in [*rows, *semantic]}.values())
            by_id = {str(row.id): row for row in rows}
            result = []
            for identifier, score in sorted(
                ranked.items(), key=lambda item: item[1], reverse=True
            )[:top_k]:
                row = by_id[identifier]
                result.append(
                    {
                        "id": identifier,
                        "document_id": str(row.document_id),
                        "version": row.version,
                        "title": row.title,
                        "source": row.source,
                        "language": row.language,
                        "content": row.content,
                        "digest": row.digest,
                        "score": score,
                        "methods": methods,
                        "corpus_limit": 1000,
                        "embedding_model": audit_settings.EMBEDDING_MODEL
                        if "pgvector_cosine_rrf" in methods
                        else None,
                    }
                )
            return result
