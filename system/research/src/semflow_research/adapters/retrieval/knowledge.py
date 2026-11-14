"""BM25 and frozen-vector cosine/RRF over an explicit corpus snapshot.

Corpus visibility and versions are resolved by the caller before this adapter.
There is no platform knowledge-table lookup, user identity or implicit index.
"""

import math
import os

os.environ.setdefault("HAYSTACK_TELEMETRY_ENABLED", "false")

from haystack import Document, Pipeline
from haystack.components.retrievers.in_memory import InMemoryBM25Retriever
from haystack.document_stores.in_memory import InMemoryDocumentStore

from semflow_research.adapters.retrieval.embedding_identity import embedding_identity
from semflow_research.adapters.retrieval.quality import active_records
from semflow_research.domain.errors import AuditError
from semflow_research.state.models import KnowledgeChunk


def cosine(left, right):
    if (
        len(left) != len(right)
        or not left
        or not all(math.isfinite(v) for v in [*left, *right])
    ):
        raise AuditError("冻结向量维度或数值不一致", code="integrity_error")
    denominator = math.sqrt(sum(x * x for x in left) * sum(x * x for x in right))
    if denominator == 0:
        raise AuditError("冻结向量不能为零向量", code="integrity_error")
    return sum(a * b for a, b in zip(left, right, strict=True)) / denominator


class KnowledgeRetriever:
    def __init__(self, *, _kernel):
        self.context = _kernel

    def retrieve(
        self,
        corpus_scope,
        language,
        query,
        top_k=6,
        api_version=None,
        mode="auto",
        corpus=None,
        query_vector=None,
        title_terms=None,
        example_cwe=None,
        document_ids=None,
        active_only=False,
    ):
        context = self.context
        if context.corpus_snapshot is None:
            raise AuditError("当前执行没有冻结的检索语料", code="materials_missing")
        if corpus_scope != context.corpus_snapshot.snapshot_id:
            raise AuditError("检索语料身份不一致", code="identity_error")
        if (
            mode not in {"auto", "bm25", "vector", "hybrid"}
            or not query
            or len(query) > 5000
        ):
            raise AuditError("检索请求或模式无效")
        # WIRE-RECV:research.run — peer: rule request/resource preparation.
        # top_k bounds each role lookup; retrieve_both combines explicit role quotas.
        # AGENT: preserve this meaning in RetrievalPolicy and the producer together.
        top_k = min(
            top_k,
            getattr(getattr(context.spec.inputs, "retrieval", None), "top_k", top_k),
        )
        rows = context.records.list(KnowledgeChunk, corpus_scope=corpus_scope)
        rows = sorted(rows, key=lambda r: r.created_at, reverse=True)
        allowed = set(map(str, document_ids)) if document_ids is not None else None
        rows = [
            r
            for r in rows
            if r.language in {language, "any"}
            and (allowed is None or str(r.document_id) in allowed)
            and (corpus is None or r.corpus == corpus)
            and (api_version is None or r.provenance.get("api_version") == api_version)
            and (not title_terms or any(term in r.title for term in title_terms))
            and (
                not example_cwe or active_only or r.provenance.get("cwe") == example_cwe
            )
            and (
                r.corpus != "rule_example"
                or active_only
                or r.provenance.get("validation", {}).get("status") != "failed"
            )
        ][:1000]
        if active_only:
            rows = active_records(rows, example_cwe)
        if not rows:
            return []
        store = InMemoryDocumentStore(
            bm25_tokenization_regex=r"(?u)[\u4e00-\u9fff]|[a-zA-Z0-9_]+"
        )
        store.write_documents([Document(id=str(r.id), content=r.content) for r in rows])
        pipeline = Pipeline()
        pipeline.add_component(
            "retrieve", InMemoryBM25Retriever(document_store=store, top_k=top_k * 2)
        )
        lexical = pipeline.run({"retrieve": {"query": query}})["retrieve"]["documents"]
        ranked = {
            doc.id: 1 / (60 + rank)
            for rank, doc in enumerate(lexical)
            if (doc.score or 0) > 0
        }
        methods = ["haystack_bm25"]
        identity = (
            embedding_identity(_kernel=context)
            if context.settings.EMBEDDING_MODEL
            else None
        )
        indexed = [
            r
            for r in rows
            if r.embedding is not None
            and r.embedding_identity == identity
            and r.embedding_model == context.settings.EMBEDDING_MODEL
        ]
        if mode != "bm25" and indexed:
            if mode == "vector":
                ranked.clear()
                methods = []
            vector = query_vector or context.model.embed([query])[0]
            semantic = sorted(
                indexed, key=lambda r: cosine(r.embedding, vector), reverse=True
            )[: top_k * 2]
            for rank, row in enumerate(semantic):
                ranked[str(row.id)] = ranked.get(str(row.id), 0) + 1 / (60 + rank)
            methods.append("frozen_vector_cosine_rrf")
        if mode in {"vector", "hybrid"} and "frozen_vector_cosine_rrf" not in methods:
            raise AuditError(
                "冻结语料没有匹配的向量索引，不能静默降级", code="materials_missing"
            )
        by_id = {str(row.id): row for row in rows}
        result, seen = [], set()
        order = sorted(
            ranked.items(),
            key=lambda item: (
                corpus == "rule_example"
                and by_id[item[0]].provenance.get("validation", {}).get("status")
                == "passed",
                item[1],
            ),
            reverse=True,
        )
        for identifier, score in order:
            row = by_id[identifier]
            if row.digest in seen:
                continue
            if len(result) >= top_k:
                break
            seen.add(row.digest)
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
                    "embedding_model": context.settings.EMBEDDING_MODEL
                    if indexed and mode != "bm25"
                    else None,
                }
            )
        return result
