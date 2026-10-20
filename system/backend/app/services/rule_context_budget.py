"""Fit whole optional RAG records without trimming source, facts or cited APIs."""

import json
from copy import deepcopy

from app.domain.audit import AuditError


def model_characters(context):
    return len(json.dumps({"untrusted_analysis_material": context}, ensure_ascii=False))


def cited_ids(value):
    if isinstance(value, str):
        return {value}
    if isinstance(value, dict):
        return set().union(*(cited_ids(item) for item in value.values()))
    if isinstance(value, list):
        return set().union(*(cited_ids(item) for item in value))
    return set()


def fit_rule_context(context, limit):
    before = model_characters(context)
    if before <= limit:
        return context
    result = deepcopy(context)
    knowledge = result["knowledge"]
    protected = cited_ids(result.get("semantic_inspection", {}))
    roles = set()
    for row in knowledge:
        role = (row["corpus"], tuple(row.get("retrieval_slot", [])))
        if role not in roles:
            protected.add(row["id"])
            roles.add(role)
    omitted = []
    while model_characters(result) > limit:
        optional = [row for row in knowledge if row["id"] not in protected]
        if not optional:
            raise AuditError(
                "目标源码、已引用证据及必要 API 仍超过上下文预算，请按单个漏洞缩小目标；原文未截断",
                code="context_budget",
            )
        removed = max(optional, key=lambda row: len(row.get("content", "")))
        knowledge.remove(removed)
        omitted.append(removed["id"])
        result["output_contract"] = {
            **result.get("output_contract", {}),
            "knowledge_ids": [row["id"] for row in knowledge],
        }
        result["materials_note"] = (
            "Project source, facts, unknowns and cited APIs remain complete. "
            "Optional RAG records were selected as whole records to fit the budget; "
            "full retrieval and provenance remain frozen in rule-materials.json. "
            "Cite only the knowledge IDs supplied in this view."
        )
        result["context_selection"] = {
            "original_characters": before,
            "limit": limit,
            "omitted_knowledge_ids": omitted,
            "full_materials_artifact": "rule-materials.json",
        }
    return result
