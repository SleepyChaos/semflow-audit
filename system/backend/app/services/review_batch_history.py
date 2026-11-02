"""Keep accepted initial verdicts and immutable revision histories in one logical batch."""

from app.domain.audit import AuditError


def merge_revision(previous, result, revision):
    result = {
        **result,
        "revision_accepted_ids": [a["candidate_id"] for a in result["assessments"]],
    }
    if not revision:
        return {**result, "revision": 0, "assessment_history": []}
    identifiers = set(revision["candidate_ids"])
    original = {a["candidate_id"]: a for a in previous.get("assessments", [])}
    if (
        revision["batch_id"] != result["batch_id"]
        or not identifiers.issubset(original)
        or any(original[i]["assessment"] != "insufficient" for i in identifiers)
        or not set(result["candidate_ids"]).issubset(identifiers)
    ):
        raise AuditError("补证目标身份或前置结论已变化", code="identity_error")
    merged = {**previous, **result}
    for key, identity in [
        ("assessments", "candidate_id"),
        ("recommendations", "id"),
        ("classifications", "candidate_id"),
    ]:
        rows = {r[identity]: r for r in previous.get(key, [])}
        rows.update({r[identity]: r for r in result.get(key, [])})
        merged[key] = list(rows.values())
    merged["candidate_ids"] = previous["candidate_ids"]
    # A rejected/omitted revision never erases an already accepted insufficient verdict.
    merged["unreviewed_candidate_ids"] = previous["unreviewed_candidate_ids"]
    merged["status"] = previous["status"]
    for key in (
        "rejected_assessments",
        "root_relations",
        "rejected_root_relations",
        "rejected_new_findings",
        "rejected_anchor_assessments",
    ):
        merged[key] = previous.get(key, []) + result.get(key, [])
    merged["revision"] = previous.get("revision", 0) + 1
    merged["assessment_history"] = [
        *previous.get("assessment_history", []),
        {k: v for k, v in previous.items() if k != "assessment_history"},
    ]
    return merged
