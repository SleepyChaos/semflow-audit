"""Algorithm extracted from app.services.knowledge_evidence.

Runtime dependencies are passed explicitly; no platform ORM or configuration.
Changes to JSON require checking the corresponding semflow_contracts/wire peer.
"""

"""Budget advisory RAG evidence without truncating selected source/API bodies."""
import json

from semflow_research.adapters.retrieval.knowledge import KnowledgeRetriever
from semflow_research.domain.errors import AuditError


def gather_knowledge(evidence, context, limit, query, *, _kernel):
    records = KnowledgeRetriever(_kernel=_kernel).retrieve(
        evidence.source_context.corpus_scope, evidence.source_context.language, query
    )
    chosen, omitted = ([], [])
    budget = limit - len(json.dumps(context, ensure_ascii=False)) - 1500
    for row in records:
        compact = {
            key: row[key]
            for key in (
                "id",
                "version",
                "title",
                "source",
                "content",
                "digest",
                "methods",
            )
        }
        compact["provenance"] = {
            key: row["provenance"].get(key)
            for key in ("trust", "api_version", "license")
        }
        content = json.dumps([*chosen, compact], ensure_ascii=False)
        if len(json.dumps(content, ensure_ascii=False)) <= budget:
            chosen.append(compact)
        else:
            omitted.append({"id": row["id"], "version": row["version"]})
    if records and (not chosen):
        raise AuditError(
            "知识原文超过剩余复审预算，请缩小范围；未截断正文", code="context_budget"
        )
    return evidence.record(
        "knowledge",
        json.dumps(chosen, ensure_ascii=False),
        {
            "chunks": [{"id": row["id"], "version": row["version"]} for row in chosen],
            "omitted_chunks": omitted,
            "scope": "Whole selected advisory chunks; unselected chunks are not read evidence",
        },
    )
