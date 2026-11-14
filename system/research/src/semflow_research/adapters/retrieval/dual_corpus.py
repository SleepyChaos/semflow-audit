"""Role-separated retrieval from a frozen corpus, without platform queries."""

import re
from uuid import UUID

from semflow_research.adapters.retrieval.embedding_identity import embedding_identity
from semflow_research.adapters.retrieval.knowledge import KnowledgeRetriever
from semflow_research.domain.errors import AuditError
from semflow_research.state.models import KnowledgeChunk


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
    *,
    _kernel,
):
    vector = None
    if mode != "bm25" and _kernel.settings.EMBEDDING_MODEL:
        indexed = [
            r
            for r in _kernel.records.list(KnowledgeChunk, corpus_scope=owner)
            if r.embedding is not None
            and r.embedding_identity == embedding_identity(_kernel=_kernel)
        ]
        if indexed:
            vector = _kernel.model.embed([query])[0]
    topics = []
    for name, cwe, patterns in [
        (
            "CodeInjection",
            "CWE-094",
            ["\\beval\\b", "code.injection", "代码注入", "CWE-0?94"],
        ),
        ("SqlInjection", "CWE-089", ["\\bSQL\\b", "SQL注入", "CWE-0?89"]),
        ("PathInjection", "CWE-022", ["path.traversal", "路径遍历", "CWE-0?22"]),
        (
            "CommandInjection",
            "CWE-078",
            ["command.injection", "命令注入", "命令执行", "CWE-0?78"],
        ),
    ]:
        if exact_cwe:
            patterns = [p + "(?!\\d)" if p.startswith("CWE-") else p for p in patterns]
        if any(re.search(pattern, query, re.IGNORECASE) for pattern in patterns):
            topics.append((name, cwe))
    if enhanced:
        if re.search(
            "\\bxss\\b|cross.site|跨站脚本|CWE-0?79" + ("(?!\\d)" if exact_cwe else ""),
            query,
            re.IGNORECASE,
        ):
            topics.append(
                ("ReflectedXSS" if language == "python" else "ReflectedXss", "CWE-079")
            )
        if re.search(
            "\\bnosql\\b|CWE-0?943" + ("(?!\\d)" if exact_cwe else ""),
            query,
            re.IGNORECASE,
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
    if (
        enhanced
        and topic
        and (topic[1] == "CWE-079")
        and (language == "python")
        and routed
    ):
        slots[0] = ("reference", 1, ["ReflectedXssQuery"], None)
    if (
        enhanced
        and topic
        and (language == "python")
        and (topic[1] == "CWE-094")
        and routed
    ):
        slots[2] = ("reference", 1, ["ApiGraphs"], None)
    if exact_cwe and routed:
        from semflow_research.adapters.retrieval.role_queries import refined_slots

        slots = refined_slots(language, topic, slots)
    result, seen, content_seen = ([], set(), set())
    for corpus, limit, title_terms, cwe in slots:
        # Peer: RetrievalPolicy.top_k caps each role, independently of routing.
        # AGENT: preserve this cap when changing role quotas or the public policy.
        limit = (
            min(limit, _kernel.spec.inputs.retrieval.top_k)
            if _kernel.spec.module == "rules"
            else limit
        )
        slot_query, slot_mode = (query, mode)
        if exact_cwe:
            from semflow_research.adapters.retrieval.role_queries import role_query

            slot_query, slot_mode = role_query(topic, title_terms, query, mode)
        records = KnowledgeRetriever(_kernel=_kernel).retrieve(
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
                row = complete_document(owner, row, _kernel=_kernel)
            from semflow_research.evidence.context_materials import digest

            content_id = digest(row["content"])
            if content_id in content_seen:
                continue
            content_seen.add(content_id)
            row["retrieval_slot"] = title_terms or ([cwe] if cwe else [corpus])
            result.append(row)
    return result


def complete_document(owner, record, *, _kernel):
    # Interface peer: contracts.corpus.CorpusManifest / public.corpus.freeze.
    # AGENT: v1 assembles every ordered chunk with two LF separators. Keep source
    # versions and complete content; do not truncate or infer current platform rows.
    rows = _kernel.records.list(
        KnowledgeChunk,
        document_id=UUID(record["document_id"]),
        version=record["version"],
        corpus="rule_example",
        corpus_scope=owner,
    )
    rows.sort(key=lambda r: r.position)
    content = "\n\n".join(r.content for r in rows)
    if not rows or len(content) > 18000:
        raise AuditError(
            "范例依赖/原文超过预算，不能截断查询", code="materials_missing"
        )
    return {
        **record,
        "content": content,
        "document_chunks": [{"id": str(r.id), "digest": r.digest} for r in rows],
        "dependency_manifest": rows[0].provenance.get("dependencies", {}),
    }
