"""Persistent, versioned knowledge with Haystack BM25 and optional pgvector fusion."""

import hashlib
import json
import math
import os
from uuid import UUID, uuid4

os.environ.setdefault("HAYSTACK_TELEMETRY_ENABLED", "False")
from haystack import Document, Pipeline
from haystack.components.retrievers.in_memory import InMemoryBM25Retriever
from haystack.document_stores.in_memory import InMemoryDocumentStore
from sqlalchemy import or_
from sqlmodel import Session, select

from app.adapters.ai.provider import CompatibleModel
from app.adapters.retrieval.chunking import semantic_chunks, source_chunks
from app.adapters.retrieval.embedding_identity import embedding_identity
from app.core.audit_config import audit_settings
from app.core.db import engine
from app.domain.audit import AuditError
from app.persistence.knowledge_models import KnowledgeChunk


def import_knowledge(
    owner_id: UUID | None,
    title: str,
    source: str,
    language: str,
    content: str,
    provenance: dict | None = None,
    corpus: str = "unclassified",
    content_format: str = "markdown",
) -> dict:
    if corpus not in {"unclassified", "reference", "rule_example"}:
        raise AuditError("知识集合无效")
    if content_format not in {"markdown", "source"} or (
        content_format == "source" and corpus != "reference"
    ):
        raise AuditError("源码切片只能用于参考知识")
    provenance = provenance or {
        "trust": "user_supplied",
        "license": "unspecified",
        "api_version": "unknown",
    }
    digest = hashlib.sha256(
        json.dumps(
            {
                "content": content,
                "provenance": provenance,
                "corpus": corpus,
                "format": content_format,
            },
            sort_keys=True,
            ensure_ascii=False,
        ).encode()
    ).hexdigest()
    with Session(engine) as session:
        existing = session.exec(
            select(KnowledgeChunk).where(
                KnowledgeChunk.owner_id == owner_id,
                KnowledgeChunk.source == source,
                KnowledgeChunk.version == digest,
            )
        ).all()
        if existing:
            return {
                "document_id": str(existing[0].document_id),
                "version": digest,
                "chunks": len(existing),
                "deduplicated": True,
            }
    document_id = uuid4()
    rows = []
    # Stable version hash; overlapping chunks retain their original exact text.
    chunks = (
        source_chunks(content)
        if content_format == "source"
        else semantic_chunks(content)
    )
    for position, text in enumerate(chunks):
        rows.append(
            KnowledgeChunk(
                owner_id=owner_id,
                document_id=document_id,
                version=digest,
                title=title,
                source=source,
                language=language,
                position=position,
                provenance=provenance,
                corpus=corpus,
                content=text,
                digest=hashlib.sha256(text.encode()).hexdigest(),
            )
        )
    with Session(engine) as session:
        session.add_all(rows)
        session.commit()
    return {"document_id": str(document_id), "version": digest, "chunks": len(rows)}


def index_document(document_id: UUID, owner_id: UUID | None) -> None:
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
                    or (
                        audit_settings.EMBEDDING_DIMENSIONS
                        and len(vector) != audit_settings.EMBEDDING_DIMENSIONS
                    )
                    or not all(math.isfinite(value) for value in vector)
                    or not any(vector)
                ):
                    raise AuditError("向量维度无效")
                row.embedding = vector
                row.embedding_model = audit_settings.EMBEDDING_MODEL
                row.embedding_identity = embedding_identity()
                row.embedding_error = None
                session.add(row)
        session.commit()


class KnowledgeRetriever:
    def retrieve(
        self,
        owner_id: UUID,
        language: str,
        query: str,
        top_k: int = 6,
        api_version: str | None = None,
        mode: str = "auto",
        corpus: str | None = None,
        query_vector: list[float] | None = None,
        title_terms: list[str] | None = None,
        example_cwe: str | None = None,
        document_ids: list[UUID] | None = None,
        active_only: bool = False,
    ) -> list[dict]:
        if mode not in {"auto", "bm25", "vector", "hybrid"}:
            raise AuditError("检索模式无效")
        if not query or len(query) > 5000:
            raise AuditError("知识检索请求无效")
        with Session(engine) as session:
            condition = (KnowledgeChunk.owner_id == owner_id) | (
                KnowledgeChunk.owner_id.is_(None)
            )
            if document_ids is not None:
                # Server-owned frozen experiment scope; ownership filters still apply.
                condition = condition & KnowledgeChunk.document_id.in_(document_ids)
            if corpus:
                if corpus not in {"reference", "rule_example"}:
                    raise AuditError("知识集合无效")
                condition = condition & (KnowledgeChunk.corpus == corpus)
                if corpus == "rule_example" and not active_only:
                    verified = KnowledgeChunk.provenance["validation"][
                        "status"
                    ].as_string()
                    condition = condition & or_(
                        verified.is_(None), verified != "failed"
                    )
            if title_terms:
                condition = condition & or_(
                    *(KnowledgeChunk.title.contains(term) for term in title_terms)
                )
            if example_cwe and not active_only:
                condition = condition & (
                    KnowledgeChunk.provenance["cwe"].as_string() == example_cwe
                )
            if api_version:
                condition = condition & (
                    KnowledgeChunk.provenance["api_version"].as_string() == api_version
                )
            rows = session.exec(
                select(KnowledgeChunk)
                .where(condition, KnowledgeChunk.language.in_([language, "any"]))
                .order_by(KnowledgeChunk.created_at.desc())
                .limit(1000)
            ).all()
            if api_version:
                rows = [
                    row
                    for row in rows
                    if row.provenance.get("api_version") == api_version
                ]
            if active_only:
                from app.adapters.retrieval.quality import active_records

                rows = active_records(rows, example_cwe)
                condition = condition & KnowledgeChunk.id.in_([row.id for row in rows])
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
            if (
                mode != "bm25"
                and audit_settings.EMBEDDING_MODEL
                and any(
                    row.embedding_model == audit_settings.EMBEDDING_MODEL
                    and row.embedding_identity == embedding_identity()
                    for row in rows
                )
            ):
                if mode == "vector":
                    ranked.clear()
                    methods = []
                vector = query_vector or CompatibleModel().embed([query])[0]
                if any(
                    len(row.embedding) != len(vector)
                    for row in rows
                    if row.embedding_model == audit_settings.EMBEDDING_MODEL
                    and row.embedding_identity == embedding_identity()
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
                        KnowledgeChunk.embedding_identity == embedding_identity(),
                        KnowledgeChunk.embedding.is_not(None),
                    )
                    .order_by(KnowledgeChunk.embedding.cosine_distance(vector))
                    .limit(top_k * 2)
                ).all()
                if api_version:
                    semantic = [
                        row
                        for row in semantic
                        if row.provenance.get("api_version") == api_version
                    ]
                for rank, row in enumerate(semantic):
                    ranked[str(row.id)] = ranked.get(str(row.id), 0) + 1 / (60 + rank)
                methods.append("pgvector_cosine_rrf")
                rows = list({row.id: row for row in [*rows, *semantic]}.values())
            if mode in {"vector", "hybrid"} and "pgvector_cosine_rrf" not in methods:
                raise AuditError("未配置或索引向量模型，不能宣称向量/混合检索")
            by_id = {str(row.id): row for row in rows}
            selected = set()
            result = []
            for identifier, score in sorted(
                ranked.items(),
                key=lambda item: (
                    corpus == "rule_example"
                    and by_id[item[0]].provenance.get("validation", {}).get("status")
                    == "passed",
                    item[1],
                ),
                reverse=True,
            ):
                row = by_id[identifier]
                if row.digest in selected:
                    continue
                if len(result) >= top_k:
                    break
                selected.add(row.digest)
                result.append(
                    {
                        "id": identifier,
                        "document_id": str(row.document_id),
                        "version": row.version,
                        "title": row.title,
                        "source": row.source,
                        "provenance": row.provenance,
                        "corpus": row.corpus,
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
