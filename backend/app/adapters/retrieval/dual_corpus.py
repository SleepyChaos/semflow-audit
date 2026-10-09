"""Separate evidence roles, exact version filters and one shared query vector."""

import re

from sqlmodel import Session, select

from app.adapters.ai.provider import CompatibleModel
from app.adapters.retrieval.embedding_identity import embedding_identity
from app.adapters.retrieval.knowledge import KnowledgeRetriever
from app.core.audit_config import audit_settings
from app.core.db import engine
from app.domain.audit import AuditError
from app.persistence.knowledge_models import KnowledgeChunk


def retrieve_both(
    owner,
    language,
    query,
    api_version,
    mode="auto",
    routed=True,
    document_ids=None,
    enhanced=False,
    exact_cwe=False,
):
    vector = None
    if mode != "bm25" and audit_settings.EMBEDDING_MODEL:
        with Session(engine) as session:
            statement = select(KnowledgeChunk.id).where(
                (KnowledgeChunk.owner_id == owner) | KnowledgeChunk.owner_id.is_(None),
                KnowledgeChunk.language.in_([language, "any"]),
                KnowledgeChunk.provenance["api_version"].as_string() == api_version,
                KnowledgeChunk.corpus.in_(["reference", "rule_example"]),
                KnowledgeChunk.embedding_identity == embedding_identity(),
                KnowledgeChunk.embedding.is_not(None),
            )
            if document_ids is not None:
                statement = statement.where(
                    KnowledgeChunk.document_id.in_(document_ids)
                )
            indexed = session.exec(statement.limit(1)).first()
        if indexed:
            vector = CompatibleModel().embed([query])[0]
    topics = []
    for name, cwe, patterns in [
        (
            "CodeInjection",
            "CWE-094",
            [r"\beval\b", r"code.injection", "代码注入", r"CWE-0?94"],
        ),
        ("SqlInjection", "CWE-089", [r"\bSQL\b", "SQL注入", r"CWE-0?89"]),
        ("PathInjection", "CWE-022", [r"path.traversal", "路径遍历", r"CWE-0?22"]),
        (
            "CommandInjection",
            "CWE-078",
            [r"command.injection", "命令注入", "命令执行", r"CWE-0?78"],
        ),
    ]:
        if exact_cwe:
            patterns = [p + r"(?!\d)" if p.startswith("CWE-") else p for p in patterns]
        if any(re.search(pattern, query, re.I) for pattern in patterns):
            topics.append((name, cwe))
    if enhanced:
        if re.search(
            r"\bxss\b|cross.site|跨站脚本|CWE-0?79" + (r"(?!\d)" if exact_cwe else ""),
            query,
            re.I,
        ):
            topics.append(
                ("ReflectedXSS" if language == "python" else "ReflectedXss", "CWE-079")
            )
        if re.search(
            r"\bnosql\b|CWE-0?943" + (r"(?!\d)" if exact_cwe else ""), query, re.I
        ):
            topics.append(("NosqlInjection", "CWE-943"))
    topic = topics[0] if len(topics) == 1 else None
    slots = [("reference", 3, None, None), ("rule_example", 2, None, None)]
    if topic and routed:
        slots = [
            ("reference", 1, [topic[0] + "Query"], None),
            ("reference", 1, [topic[0] + "Customizations"], None),
            ("reference", 1, ["ApiGraphs", "DataFlow", "TaintTracking"], None),
            ("rule_example", 2, None, topic[1]),
        ]
    if enhanced and topic and topic[1] == "CWE-079" and language == "python" and routed:
        slots[0] = ("reference", 1, ["ReflectedXssQuery"], None)
    if enhanced and topic and language == "python" and topic[1] == "CWE-094" and routed:
        slots[2] = ("reference", 1, ["ApiGraphs"], None)
    if exact_cwe and routed:
        from app.adapters.retrieval.role_queries import refined_slots

        slots = refined_slots(language, topic, slots)
    result, seen, content_seen = [], set(), set()
    for corpus, limit, title_terms, cwe in slots:
        slot_query, slot_mode = query, mode
        if exact_cwe:
            from app.adapters.retrieval.role_queries import role_query

            slot_query, slot_mode = role_query(topic, title_terms, query, mode)
        records = KnowledgeRetriever().retrieve(
            owner,
            language,
            "moduleImport getMember getACall"
            if enhanced and title_terms == ["ApiGraphs"]
            else slot_query,
            top_k=limit,
            api_version=api_version,
            mode="bm25" if enhanced and title_terms == ["ApiGraphs"] else slot_mode,
            corpus=corpus,
            query_vector=vector,
            title_terms=title_terms,
            example_cwe=cwe,
            document_ids=document_ids,
            active_only=enhanced,
        )
        if not records:
            raise AuditError(
                f"{corpus} 没有匹配版本材料，需先补知识/范例", code="materials_missing"
            )
        for row in records:
            key = (
                (row["document_id"], row["version"])
                if corpus == "rule_example"
                else (row["id"], row["version"])
            )
            if key in seen:
                continue
            seen.add(key)
            if corpus == "rule_example":
                row = complete_document(owner, row)
            from app.services.context_materials import digest

            content_id = digest(row["content"])
            if content_id in content_seen:
                continue
            content_seen.add(content_id)
            row["retrieval_slot"] = title_terms or ([cwe] if cwe else [corpus])
            result.append(row)
    return result


def complete_document(owner, record):
    from uuid import UUID

    with Session(engine) as session:
        rows = session.exec(
            select(KnowledgeChunk)
            .where(
                KnowledgeChunk.document_id == UUID(record["document_id"]),
                KnowledgeChunk.version == record["version"],
                KnowledgeChunk.corpus == "rule_example",
                (KnowledgeChunk.owner_id == owner) | KnowledgeChunk.owner_id.is_(None),
            )
            .order_by(KnowledgeChunk.position)
        ).all()
    content = "\n\n".join(row.content for row in rows)
    if not rows or len(content) > 18000:
        raise AuditError("范例依赖/原文超出预算，需缩小范例；不截断查询")
    return {
        **record,
        "content": content,
        "document_chunks": [{"id": str(r.id), "digest": r.digest} for r in rows],
        "dependency_manifest": rows[0].provenance.get("dependencies", {}),
    }
