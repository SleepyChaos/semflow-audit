"""Select visible current platform documents once, then freeze complete research data."""

import hashlib
from collections import defaultdict
from datetime import UTC
from types import SimpleNamespace

from semflow_contracts.corpus import CorpusDocument, CorpusManifest, vector_digest
from semflow_contracts.rule_values import EmbeddingIdentity
from semflow_research.public.artifacts import LocalArtifacts
from semflow_research.public.corpus import freeze
from sqlmodel import select

from app.domain.audit import AuditError
from app.persistence.knowledge_models import KnowledgeChunk
from app.research_bridge.requests import research_root


def capture(session, binding, audit, resources, experiment):
    rows = session.exec(
        select(KnowledgeChunk)
        .where(
            (KnowledgeChunk.owner_id == audit.owner_id)
            | KnowledgeChunk.owner_id.is_(None),
            KnowledgeChunk.corpus.in_(["reference", "rule_example"]),
            KnowledgeChunk.language.in_([audit.language, "any"]),
        )
        .order_by(KnowledgeChunk.created_at.desc(), KnowledgeChunk.id)
    ).all()
    latest = {}
    selected = experiment.get("corpus_document_ids")
    groups = defaultdict(list)
    for row in rows:
        key = (row.owner_id, row.source)
        latest.setdefault(key, row.version)
        if row.version == latest[key] and (
            selected is None or str(row.document_id) in set(map(str, selected))
        ):
            groups[(row.document_id, row.version)].append(row)
    if selected is not None and not set(map(str, selected)).issubset(
        {str(key[0]) for key in groups}
    ):
        raise AuditError("指定语料文档不可见或非当前版本", code="target_not_authorized")
    from app.adapters.retrieval.embedding_identity import embedding_identity

    identity = embedding_identity(resources)
    mode = experiment.get("retrieval_mode", "auto")
    indexed = [
        row
        for rows in groups.values()
        for row in rows
        if row.embedding is not None and row.embedding_identity == identity
    ]
    if mode == "auto":
        mode = "hybrid" if resources.EMBEDDING_MODEL and indexed else "bm25"
    if mode in {"vector", "hybrid"} and not indexed:
        raise AuditError("冻结语料没有匹配的向量索引", code="resource_unavailable")
    documents = []
    for group in groups.values():
        group.sort(key=lambda row: row.position)
        first = group[0]
        if [row.position for row in group] != list(range(len(group))):
            raise AuditError("语料分块不完整", code="integrity_error")
        for row in group:
            if hashlib.sha256(row.content.encode()).hexdigest() != row.digest:
                raise AuditError("知识分块内容与摘要不同", code="integrity_error")
        documents.append(
            CorpusDocument(
                document_id=first.document_id,
                collection=first.corpus,
                version=first.version,
                title=first.title,
                source=first.source,
                language=first.language,
                created_at=first.created_at.replace(tzinfo=UTC)
                if first.created_at.tzinfo is None
                else first.created_at,
                chunks=tuple(row.content for row in group),
                provenance={
                    **first.provenance,
                    "corpus_origin_scope": "public"
                    if first.owner_id is None
                    else "workspace",
                },
                vectors=tuple(
                    tuple(row.embedding) if row in indexed else None for row in group
                )
                if mode != "bm25"
                else None,
            )
        )
    embedding = None
    if mode != "bm25":
        if (
            not indexed
            or not resources.EMBEDDING_MODEL
            or not resources.EMBEDDING_REVISION
        ):
            raise AuditError("冻结向量检索资源不足", code="resource_unavailable")
        matrix = [
            SimpleNamespace(
                document_id=doc.document_id,
                version=doc.version,
                position=position,
                content=SimpleNamespace(
                    sha256=hashlib.sha256(text.encode()).hexdigest()
                ),
                vector=doc.vectors[position],
            )
            for doc in documents
            for position, text in enumerate(doc.chunks)
        ]
        embedding = EmbeddingIdentity(
            provider="openai-compatible",
            model=resources.EMBEDDING_MODEL,
            revision=resources.EMBEDDING_REVISION,
            dimensions=resources.EMBEDDING_DIMENSIONS,
            index_digest=vector_digest(matrix),
        )
    # WIRE-SEND:research.corpus — peer: corpus_inputs.materialize / dual_corpus.
    # AGENT: select visibility/version before freezing, retain every chunk and
    # its existing validation provenance; no later live ORM lookup in the kernel.
    snapshot = freeze(
        documents,
        root=research_root(),
        owner_execution_id=binding.execution_id,
        embedding=embedding,
    )
    manifest = CorpusManifest.model_validate_json(
        LocalArtifacts(research_root() / "artifacts", binding.execution_id).read(
            snapshot.manifest
        )
    )
    ids = {
        (row.document_id, row.position): row.id
        for group in groups.values()
        for row in group
    }
    binding.entity_map = {
        **binding.entity_map,
        **{
            f"knowledge/{chunk.chunk_id}": str(ids[(chunk.document_id, chunk.position)])
            for chunk in manifest.chunks
        },
    }
    return snapshot, mode
