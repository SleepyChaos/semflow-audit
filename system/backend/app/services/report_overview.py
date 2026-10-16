"""Project-wide report material, sent once rather than per vulnerability."""

from app.services.report_materials import coverage_summary, excerpt, review_context


def overview_material(source):
    candidates = source["candidates"]
    return {
        "batch": {"scope": "global"},
        "audit": {k: v for k, v in source["audit"].items() if k != "findings"},
        "summary": source["summary"],
        "coverage": coverage_summary(source["coverage"]),
        # The overview must not generate duplicate issue narratives. Its review
        # summary retains classifications and unresolved premises for all issues.
        "candidates": [],
        "required_candidate_ids": [],
        "evidence": [],
        "issue_evidence_binding": {},
        "review_summary": [
            {
                "id": row["id"],
                "title": row["title"],
                "location": row.get("location"),
                "classification": row.get("classification"),
                "review": excerpt(
                    {
                        key: value
                        for key, value in (row.get("review") or {}).items()
                        if key
                        in {
                            "status",
                            "reason",
                            "missing_premises",
                            "runtime_unknowns",
                            "evaluated",
                        }
                    },
                    600,
                ),
            }
            for row in candidates
        ],
        "review_context": review_context(source, candidates),
        "repairs": [repair_summary(row) for row in source["repairs"]],
        "verification": excerpt(source.get("verification", []), 1000),
        "rules": excerpt(source["rules"], 1000),
        "stages": source["stages"],
        "material_scope": "全局汇总；补丁仅提供文件、修改目的和真实验证状态，完整 diff 与历史保留在本地报告中。节选与未执行不能作为已验证事实。",
    }


def repair_summary(row):
    summary = {
        key: row.get(key)
        for key in (
            "id",
            "stage_id",
            "status",
            "candidate_ids",
            "acceptance_reason",
            "accepted_by",
        )
    }
    summary["changes"] = [
        {"file": change.get("file"), "reason": excerpt(change.get("reason"), 600)}
        for change in row.get("changes", [])
    ]
    summary["validation"] = excerpt(row.get("validation", {}), 1000)
    return summary
