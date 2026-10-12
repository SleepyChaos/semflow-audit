"""Summarize all requests; conditional detector metrics never hide failures."""

import argparse
import collections
import json
import statistics
from pathlib import Path


def summarize(report):
    groups = {}
    for row in report["records"]:
        groups.setdefault(row["arm"], []).append(row)
    result = {}
    for arm, rows in sorted(groups.items()):
        compile_count = sum(bool(row["rules"]) for row in rows)
        executable = [
            row
            for row in rows
            if row.get("oracle", {}).get("status") in ("passed", "failed")
        ]
        tp = sum(row["oracle"]["tp"] for row in executable)
        fp = sum(row["oracle"]["fp"] for row in executable)
        fn = sum(row["oracle"]["fn"] for row in executable)
        per_case = {}
        for row in rows:
            counts = per_case.setdefault(
                row["case"],
                {
                    "requests": 0,
                    "generated": 0,
                    "independent_pass": 0,
                    "dev_pass": 0,
                    "end_to_end_pass": 0,
                },
            )
            counts["requests"] += 1
            counts["generated"] += bool(row["rules"])
            counts["independent_pass"] += (
                row.get("oracle", {}).get("status") == "passed"
            )
            counts["dev_pass"] += row.get("dev_oracle", {}).get("status") == "passed"
            counts["end_to_end_pass"] += (
                bool(row["rules"])
                and row.get("oracle", {}).get("status") == "passed"
                and row.get("dev_oracle", {}).get("status") == "passed"
            )
        calls = [call for row in rows for call in row["stage"]["model_calls"]]
        result[arm] = {
            "requests": len(rows),
            "generated": compile_count,
            "independent_executed": len(executable),
            "independent_pass": sum(
                row["oracle"]["status"] == "passed" for row in executable
            ),
            "dev_pass": sum(
                row.get("dev_oracle", {}).get("status") == "passed" for row in rows
            ),
            "end_to_end_pass": sum(
                count["end_to_end_pass"] for count in per_case.values()
            ),
            "conditional_tp": tp,
            "conditional_fp": fp,
            "conditional_fn": fn,
            "conditional_precision": tp / (tp + fp) if tp + fp else None,
            "conditional_recall": tp / (tp + fn) if tp + fn else None,
            "generation_median_seconds": statistics.median(
                row["generation_seconds"] for row in rows
            ),
            "model_calls": len(calls),
            "input_tokens": sum(call.get("input_tokens") or 0 for call in calls),
            "output_tokens": sum(call.get("output_tokens") or 0 for call in calls),
            "finish_reasons": dict(
                collections.Counter(call.get("finish_reason") for call in calls)
            ),
            "failure_codes": dict(
                collections.Counter(
                    row["stage"].get("error") for row in rows if not row["rules"]
                )
            ),
            "per_case": per_case,
        }
    pairs = {}
    for left, right in [
        ("A_bm25_log", "B_routed_log"),
        ("C_bm25_candidate", "D_routed_candidate"),
        ("A_bm25_log", "C_bm25_candidate"),
        ("B_routed_log", "D_routed_candidate"),
        ("C_bm25_candidate", "E_spec_bm25"),
        ("D_routed_candidate", "F_spec_routed"),
        ("E_spec_bm25", "F_spec_routed"),
        ("I_spec_grounded", "J_spec_no_domain"),
    ]:
        if left not in result or right not in result:
            continue
        comparisons = {}
        for metric in ("generated", "independent_pass", "end_to_end_pass"):
            differences = [
                result[right]["per_case"][case][metric]
                / result[right]["per_case"][case]["requests"]
                - values[metric] / values["requests"]
                for case, values in result[left]["per_case"].items()
            ]
            comparisons[metric] = {
                "mean_task_difference": statistics.mean(differences),
                "task_differences": differences,
                "right_better_tasks": sum(value > 0 for value in differences),
                "left_better_tasks": sum(value < 0 for value in differences),
                "tied_tasks": sum(value == 0 for value in differences),
            }
        pairs[left + " -> " + right] = comparisons
    return {
        "groups": result,
        "paired_task_differences": pairs,
        "baseline": report.get("baseline", []),
        "interpretation": "Small repeated-task calibration. Conditional precision/recall only for completed tools. No population confidence claims; repeated runs are not independent vulnerabilities.",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    output = args.output
    result = summarize(json.loads((output / "report.json").read_text()))
    deviations = output / "protocol-deviations"
    result["protocol_deviation_requests"] = (
        len(list(deviations.glob("*.json"))) if deviations.exists() else 0
    )
    (output / "summary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2)
    )
    for arm, stats in result["groups"].items():
        print(
            arm,
            stats["requests"],
            stats["generated"],
            stats["independent_pass"],
            stats["dev_pass"],
            stats["end_to_end_pass"],
            round(stats["generation_median_seconds"], 2),
            flush=True,
        )


if __name__ == "__main__":
    main()
