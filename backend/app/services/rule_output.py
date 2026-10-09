"""Server-owned rule identity; preserve original model output before adaptation."""

import hashlib
import re

from app.domain.audit import AuditError
from app.services.context_materials import save_json


def assign_namespace(response, pack, *, unique_logic=False):
    save_json(pack / "model-candidate.json", response.model_dump(mode="json"))
    match = re.search(r"@id\s+(\S+)", response.query)
    if not match or (
        not unique_logic and re.fullmatch(r"(?:custom|audit)/[a-z0-9/-]+", match[1])
    ):
        return response
    # Metadata changes only: no QL logic, locations or purpose are repaired here.
    from app.adapters.codeql.custom import query_digest

    identifier = "audit/generated-" + (
        query_digest(response.query, response.modules)[:16]
        if unique_logic
        else hashlib.sha256(response.query.encode()).hexdigest()[:16]
    )
    query = (
        response.query[: match.start(1)] + identifier + response.query[match.end(1) :]
    )
    save_json(
        pack / "metadata-adaptation.json",
        {
            "field": "id",
            "original": match[1],
            "assigned": identifier,
            "meaning": "Server-owned namespace only; detection logic unchanged",
        },
    )
    return response.model_copy(update={"query": query})


def verify_module_imports(response):
    """Unreferenced source models do not participate in a detector's flow."""
    remaining = {
        name.removesuffix(".qll"): text for name, text in response.modules.items()
    }
    frontier = [response.query]
    while frontier:
        text = frontier.pop()
        names = re.findall(
            r"^\s*(?:private\s+)?import\s+([A-Za-z0-9_:/.]+)", text, re.MULTILINE
        )
        for name in names:
            local = name.split("::", 1)[0]
            if local in remaining:
                frontier.append(remaining.pop(local))
    if remaining:
        raise AuditError(
            "建模模块未被查询导入，不会参与检测：" + ", ".join(sorted(remaining))
        )
