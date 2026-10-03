"""Summarize bounded live runs; failed attempts stay in all-attempt denominators."""

import json
import re
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main():
    report = next((ROOT / "artifacts/benchmarks").glob("live-model-*/report.json"))
    data = json.loads(report.read_text())
    stages = data["stages"]
    repair_rows = []
    for stage in [s for s in stages if s["kind"] == "repair"]:
        tests = stage["result"].get("validation", {}).get("isolated_tests", {})
        match = re.search(r"ORACLE_JSON=(\{[^\n]+\})", tests.get("output", ""))
        oracle = json.loads(match[1]) if match else None
        repair_rows.append(
            {
                "case": stage["case"],
                "round": stage["round"],
                "stage_status": stage["status"],
                "oracle": oracle,
                "both_passed": stage["status"] == "completed"
                and tests.get("status") == "passed"
                and oracle == {"security": 0, "functional": 0},
                "original_unchanged": stage["result"].get(
                    "original_snapshot_unchanged"
                ),
                "acceptance": stage["result"].get("status"),
                "stage_id": stage["stage_id"],
            }
        )
    result = {
        "scope": "Small-sample real-model calibration; repeat runs are not independent samples",
        "model": data["model"],
        "actual_smoke_model": "deepseek-v4-1-flash-260910",
        "max_output_tokens": 6000,
        "embedding_configured": False,
        "raw_report": str(report.relative_to(ROOT)),
        "stage_count": len(stages),
        "usage": {
            k: sum(s["usage"].get(k, 0) for s in stages)
            for k in ["calls", "input_tokens", "output_tokens"]
        },
        "failures": [
            {
                "case": s["case"],
                "round": s["round"],
                "kind": s["kind"],
                "error": s["error"],
                "stage_id": s["stage_id"],
            }
            for s in stages
            if s["status"] == "failed"
        ],
        "repairs": repair_rows,
        "repair_all_attempt_success_rate": sum(r["both_passed"] for r in repair_rows)
        / len(repair_rows),
        "audit_timings": data["audits"],
        "timing": {},
    }
    for kind in ["review", "repair", "rule"]:
        rows = [s for s in stages if s["kind"] == kind and not s.get("phase")]
        result["timing"][kind] = {
            "attempts": len(rows),
            "median_seconds": statistics.median(s["seconds"] for s in rows),
            "min_seconds": min(s["seconds"] for s in rows),
            "max_seconds": max(s["seconds"] for s in rows),
        }
    result["review_target_scope"] = {
        "cwe": "094/095 eval code execution only; not all-CWE accuracy",
        "baseline_attempts": 18,
        "baseline_completed": 17,
        "followup_attempts": 3,
        "followup_completed": 2,
        "target_positive_supported": 6,
        "target_negative_semantically_excluded": 13,
        "failed_unknown": 2,
        "grade_method": "Evaluator checked recommendations plus candidate descriptions. JS shadowed.js supported XSS is a separate finding, and explicitly excludes built-in eval; not a code-execution FP. No completed target-eval misclassification found. Full-scope alerts are not completely annotated.",
    }
    result["rules"] = []
    validation = report.parent / "rule-validation.json"
    if validation.exists():
        for row in json.loads(validation.read_text()):
            rule = row["rule"]
            result["rules"].append(
                {
                    "id": rule["id"],
                    "hash": rule["query_hash"],
                    "stage_status": row["stage_status"],
                    "validation": rule["validation"].get("status"),
                    "validation_seconds": row["validation_seconds"],
                    "holdout_seconds": row["holdout_seconds"],
                    "holdout_locations": row["holdout_locations"],
                    "published": bool(rule["published_at"]),
                    "meaning": row["holdout_meaning"],
                }
            )
    output = ROOT / "docs/research/live-model-summary.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(output)


if __name__ == "__main__":
    main()
