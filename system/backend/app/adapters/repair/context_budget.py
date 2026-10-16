"""A soft context target can expand only for source, within a frozen ceiling."""


def context_limits(purpose, payload, policy, characters):
    preferred = policy["context_chars"]
    ceiling = max(preferred, policy.get("repair_context_max_chars", preferred))
    rows = payload.get("evidence", [])
    if not isinstance(rows, list):
        rows = []
    inspection = payload.get("inspection", {})
    if isinstance(inspection, dict):
        rows = [*rows, *inspection.get("evidence", [])]
    source = sum(
        len(row.get("content", ""))
        for row in rows
        if isinstance(row, dict)
        and row.get("kind") == "code"
        and row.get("reference", {})
        .get("file", "")
        .endswith((".py", ".js", ".jsx", ".ts", ".tsx"))
        and not row.get("content", "").startswith("See exact allowed_files")
    )
    source += sum(
        len(body)
        for name, body in payload.get("allowed_files", {}).items()
        if name.endswith((".py", ".js", ".jsx", ".ts", ".tsx"))
        and isinstance(body, str)
        and not body.startswith("Exact source is supplied once")
    )
    expansion = (
        purpose == "repair"
        and characters > preferred
        and source > 0
        and characters - source <= preferred
    )
    effective = ceiling if expansion else preferred
    return {
        "limit": effective,
        "preferred_limit": preferred,
        "frozen_ceiling": ceiling if purpose == "repair" else preferred,
        "source_characters": source,
        "status": "rejected_context"
        if characters > effective
        else "expanded_for_source"
        if expansion
        else "within_context",
        "expansion_reason": "Exact supplied source exceeds preferred target; non-source overhead remains within target"
        if expansion
        else None,
    }
