"""Algorithm extracted from app.adapters.retrieval.rule_routing.

Runtime dependencies are passed explicitly; no platform ORM or configuration.
Changes to JSON require checking the corresponding semflow_contracts/wire peer.
"""

"""Version-pinned, role-separated retrieval; no hidden holdout inputs."""
import re

from semflow_research.adapters.retrieval.knowledge import KnowledgeRetriever
from semflow_research.domain.errors import AuditError

OPERATIONS = {
    "eval": ("CodeInjection", "code-injection"),
    "sql": ("SqlInjection", "sql-injection"),
    "xss": ("ReflectedXss", "cross-site-scripting"),
}


def operation_for(requirement: str) -> str:
    matches = []
    for key, aliases in {
        "eval": ("\\beval\\b", "code.injection", "代码注入"),
        "sql": ("\\bsql\\b", "sql.injection", "SQL注入"),
        "xss": ("\\bxss\\b", "cross.site", "跨站脚本"),
    }.items():
        if any(re.search(pattern, requirement, re.IGNORECASE) for pattern in aliases):
            matches.append(key)
    if len(matches) != 1:
        raise AuditError("受限规则原型要求明确且唯一的 eval/SQL/XSS 类型")
    return matches[0]


def retrieve_rule_roles(owner, language, requirement, api_version, *, _kernel):
    operation = operation_for(requirement)
    name, _ = OPERATIONS[operation]
    retriever = KnowledgeRetriever(_kernel=_kernel)
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
            if (
                role != "types"
                and name + ("Query" if role == "query" else "Customizations")
                not in row["content"]
            ):
                continue
            if role == "types" and (
                not any(
                    symbol in row["title"].lower()
                    for symbol in ("conversion", "declaration")
                )
            ):
                continue
            if row["id"] not in selected:
                selected[row["id"]] = {**row, "roles": [role]}
            else:
                selected[row["id"]]["roles"].append(role)
            if sum(role in item["roles"] for item in selected.values()) >= 2:
                break
    return list(selected.values())[:6]
