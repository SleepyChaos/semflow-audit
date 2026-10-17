"""Project execution facts for reports, without repeated SARIF and test logs."""

from collections import Counter

from app.services.report_materials import excerpt


def validation_summary(validation):
    result = {}
    for name, check in validation.items():
        if not isinstance(check, dict):
            continue
        result[name] = {
            key: excerpt(check[key], 600)
            for key in (
                "status",
                "profile",
                "exit_code",
                "error",
                "semantic_limit",
                "workspace_snapshot",
                "patched_snapshot_hash",
                "meaning",
                "remaining_target_rules",
                "unvalidated_files",
            )
            if key in check
        }
        for key in ("findings", "new_rule_alerts"):
            if key in check:
                result[name][f"{key}_count"] = len(check[key])
        if check.get("status") == "failed" and check.get("output"):
            result[name]["failure_reason"] = excerpt(check["output"], 400)
    return result


def verification_summary(row):
    comparison = row.get("comparison") or {}
    cases = comparison.get("cases") or []
    counts = Counter(
        (case.get("category"), case.get("before"), case.get("after")) for case in cases
    )
    reasons = Counter(case["reason"] for case in cases if case.get("reason"))
    return {
        "repair_id": row.get("repair_id"),
        "comparison": {
            **{
                key: excerpt(comparison[key], 800)
                for key in (
                    "status",
                    "stage_id",
                    "summary",
                    "error",
                    "repetitions",
                    "suite_created_before_repair",
                    "identity",
                    "assumptions",
                )
                if key in comparison
            },
            "case_count": len(cases),
            "case_results": [
                {"category": category, "before": before, "after": after, "count": count}
                for (category, before, after), count in counts.items()
            ],
            "reasons": [
                {"reason": excerpt(reason, 400), "count": count}
                for reason, count in reasons.items()
            ],
            "unstable_cases": sum(case.get("stable") is False for case in cases),
            "run_count": len(comparison.get("runs") or []),
        },
    }


def rule_summary(row):
    validation = row.get("validation") or {}
    return {
        "id": row.get("id"),
        "title": row.get("title"),
        "status": row.get("status"),
        "validation": {
            **{
                key: validation[key]
                for key in ("status", "compile", "meaning")
                if key in validation
            },
            "checks": validation_summary(
                {
                    key: validation[key]
                    for key in (
                        "independent_holdout",
                        "project_replay",
                        "development",
                    )
                    if key in validation
                }
            ),
            "tests": validation_summary(validation.get("tests") or {}),
        },
    }
