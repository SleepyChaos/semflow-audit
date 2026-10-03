"""Version-pinned, role-separated retrieval; no hidden holdout inputs."""

import re

from app.adapters.retrieval.knowledge import KnowledgeRetriever
from app.domain.audit import AuditError

OPERATIONS = {
    "eval": ("CodeInjection", "code-injection"),
    "sql": ("SqlInjection", "sql-injection"),
    "xss": ("ReflectedXss", "cross-site-scripting"),
}


def operation_for(requirement: str) -> str:
    matches = []
    for key, aliases in {
        "eval": (r"\beval\b", r"code.injection", "代码注入"),
        "sql": (r"\bsql\b", "sql.injection", "SQL注入"),
        "xss": (r"\bxss\b", "cross.site", "跨站脚本"),
    }.items():
        if any(re.search(pattern, requirement, re.I) for pattern in aliases):
            matches.append(key)
    if len(matches) != 1:
        raise AuditError("受限规则原型要求明确且唯一的 eval/SQL/XSS 类型")
    return matches[0]


def retrieve_rule_roles(owner, language, requirement, api_version):
    operation = operation_for(requirement)
    name, _ = OPERATIONS[operation]
    retriever = KnowledgeRetriever()
    queries = [
        ("query", f"{name}Query"),
        ("model", f"{name}Customizations"),
        ("types", "AST dataflow conversion Node CfgNode ExprNode"),
    ]
    selected = {}
    for role, query in queries:
        for row in retriever.retrieve(
            owner, language, query, top_k=8, api_version=api_version, mode="bm25"
        ):
            # BM25 alone may return other vulnerability APIs; exact symbol gates
            # query/model evidence, while generic type declarations stay reusable.
            if (
                role != "types"
                and name + ("Query" if role == "query" else "Customizations")
                not in row["content"]
            ):
                continue
            if role == "types" and not any(
                symbol in row["title"].lower()
                for symbol in ("conversion", "declaration")
            ):
                continue
            if row["id"] not in selected:
                selected[row["id"]] = {**row, "roles": [role]}
            else:
                selected[row["id"]]["roles"].append(role)
            if sum(role in item["roles"] for item in selected.values()) >= 2:
                break
    return list(selected.values())[:6]
