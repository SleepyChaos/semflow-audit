"""Final exact-CWE comparison only after both frozen acceptance runs complete."""

import argparse
import json
import math
import statistics
from collections import Counter
from pathlib import Path

from scripts.benchmarks.formal_scoring import score_cases

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "artifacts/research/owasp48/20261007-evolution"


def read(path):
    return json.loads(path.read_text())


def compact(score):
    categories = sorted({r["category"] for r in score["cases"]})
    by_class = []
    for category in categories:
        rows = [r for r in score["cases"] if r["category"] == category]
        counts = {
            key: sum(r["classification"] == key for r in rows)
            for key in ("TP", "FP", "TN", "FN")
        }
        tp, fp, tn, fn = (counts[k] for k in ("TP", "FP", "TN", "FN"))
        by_class.append(
            {
                "category": category,
                "counts": counts,
                "TPR": tp / (tp + fn),
                "FPR": fp / (fp + tn),
                "J": tp / (tp + fn) - fp / (fp + tn),
            }
        )
    return {
        key: score[key]
        for key in ("counts", "precision", "recall", "f1", "false_positive_rate")
    } | {
        "macro_TPR": statistics.mean(c["TPR"] for c in by_class),
        "macro_FPR": statistics.mean(c["FPR"] for c in by_class),
        "macro_J": statistics.mean(c["J"] for c in by_class),
        "by_class": by_class,
        "outside_target_count": len(score["outside_target_alerts"]),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--final-version", required=True)
    args = parser.parse_args()
    decision = read(OUT / "candidate-decision.json")
    assert args.final_version == decision["chosen"], "Respect pre-acceptance selection"
    for version in ("base", args.final_version):
        integrity = read(OUT / "runs" / version / "acceptance-01/integrity.json")
        assert integrity["input_and_implementation_unchanged"]
        assert integrity["model_labels"] is False
        assert (OUT / "runs" / version / "acceptance-01/evaluation.json").exists()
    labels = read(OUT / "samples/acceptance-01/evaluator-selection.json")["selected"]
    rows = []
    static = read(OUT / "static/acceptance-01/result.json")
    codeql = score_cases(labels, static["rounds"][0]["findings"])
    rows.append(
        {
            "tool": "CodeQL fixed code-scanning suite",
            "metrics": compact(codeql),
            "wall_seconds": static["wall_seconds"],
            "query_seconds": static["rounds"][0]["query_seconds"],
            "model_calls": 0,
            "model_tokens": 0,
            "cache": "new 48-case DB; OS cache not cleared; extraction plus first query",
        }
    )
    bandit = read(OUT / "comparators/bandit/acceptance-01/result.json")
    assert all(r["status"] == "succeeded" for r in bandit["records"])
    score = score_cases(labels, bandit["records"][0]["findings"])
    rows.append(
        {
            "tool": bandit["tool"],
            "metrics": compact(score),
            "wall_seconds": statistics.median(r["seconds"] for r in bandit["records"]),
            "wall_repetitions": [r["seconds"] for r in bandit["records"]],
            "model_calls": 0,
            "model_tokens": 0,
            "cache": "three independent processes; warm OS/import effects disclosed",
        }
    )
    paired = {}
    for version in ("base", args.final_version):
        evaluation = read(OUT / "runs" / version / "acceptance-01/evaluation.json")
        assert (OUT / "runs" / version / "acceptance-01/integrity.json").exists()
        paired[version] = evaluation["scores"]["Platform_supported"]
        usage = evaluation["usage"]
        rows.append(
            {
                "tool": "Platform " + version,
                "metrics": compact(paired[version]),
                "ai_wall_seconds": evaluation["parallel_wall_seconds"],
                "wall_seconds": evaluation["parallel_wall_seconds"]
                + static["wall_seconds"],
                "timing_basis": "Sum of measured AI wall and common static scan wall; static result shared by both versions. Excludes research registration/setup; not process or GUI end-to-end wall.",
                "model_calls": usage["calls"],
                "input_tokens": usage["input_tokens"],
                "output_tokens": usage["output_tokens"],
                "model_tokens": usage["input_tokens"] + usage["output_tokens"],
                "unreviewed_candidates": evaluation["unreviewed"],
                "incomplete_case_windows": sum(
                    c["windows"] != c["inspected"] for c in evaluation["coverage"]
                ),
                "case_task_conclusions": dict(
                    sum(
                        (Counter(c["tasks"]) for c in evaluation["coverage"]),
                        Counter(),
                    )
                ),
                "cache": "actual model requests; no cross-run verdict reuse",
            }
        )
        if version == args.final_version:
            scout_score = evaluation["scores"]["Scout_raw"]
            scout_usage = {"calls": 0, "input_tokens": 0, "output_tokens": 0}
            scout_seconds = 0
            for group in (OUT / "runs" / version / "acceptance-01").glob("batch-*"):
                s = read(group / "scout.json")
                for k in scout_usage:
                    scout_usage[k] += s["stage"]["usage"].get(k, 0)
                scout_seconds += s["wall_seconds"]
            rows.append(
                {
                    "tool": "Platform independent Scout (unverified)",
                    "metrics": compact(scout_score),
                    "wall_seconds": None,
                    "summed_stage_seconds_not_parallel_wall": scout_seconds,
                    "model_calls": scout_usage["calls"],
                    "input_tokens": scout_usage["input_tokens"],
                    "output_tokens": scout_usage["output_tokens"],
                    "model_tokens": scout_usage["input_tokens"]
                    + scout_usage["output_tokens"],
                    "cache": "same final-run Scout outputs, not a separately scheduled pure-prompt tool",
                }
            )
    directory = OUT / "competitors/ocr-acceptance01"
    ocr = read(directory / "receipt.json")
    assert ocr["status"] == "completed" and len(ocr["session"]["completed_paths"]) == 48
    parsed = read(directory / "parsed.json")
    score = score_cases(labels, parsed["findings"])
    session = ocr["session"]
    rows.append(
        {
            "tool": "Alibaba Open Code Review " + ocr["ocr_commit"][:8],
            "metrics": compact(score),
            "wall_seconds": ocr["wall_seconds"],
            "model_calls": session["llm_requests"],
            "input_tokens": session["input_tokens"],
            "output_tokens": session["output_tokens"],
            "model_tokens": session["input_tokens"] + session["output_tokens"],
            "reported_cache_read_tokens": ocr.get("summary", {}).get(
                "cache_read_tokens"
            ),
            "tool_calls": ocr["tool_calls"]["total"],
            "comments": ocr["summary"]["comments"],
            "unclassified_comments": len(parsed["unclassified_comments"]),
            "completed_cases": 48,
            "unreviewed_candidates": None,
            "limits": "real full-file default OCR plan/dedup/summary; explicit CWE regex frozen before run; soft 1.8M token cap, default tool-round cap differs; non-CWE comments are not silently adjudicated",
        }
    )
    old = {r["task_id"]: r for r in paired["base"]["cases"]}
    new = {r["task_id"]: r for r in paired[args.final_version]["cases"]}
    gained = [
        key
        for key in old
        if old[key]["classification"] in {"FP", "FN"}
        and new[key]["classification"] in {"TP", "TN"}
    ]
    lost = [
        key
        for key in old
        if old[key]["classification"] in {"TP", "TN"}
        and new[key]["classification"] in {"FP", "FN"}
    ]
    n = len(gained) + len(lost)
    exact_p = (
        min(
            1,
            2
            * sum(math.comb(n, i) for i in range(min(len(gained), len(lost)) + 1))
            / 2**n,
        )
        if n
        else 1
    )
    report = {
        "sample": "acceptance-01",
        "cases": 48,
        "positive": 24,
        "negative": 24,
        "seed": 2026100748,
        "final_version": args.final_version,
        "rows": rows,
        "paired_changes": {
            "improved_cases": gained,
            "regressed_cases": lost,
            "mcnemar_two_sided_exact_p": exact_p,
        },
        "same_model": "deepseek-v4.1-flash",
        "official_scorecard": False,
        "scope": "OWASP Python balanced representative sample, exact file+CWE; one model run per config. Same-distribution public synthetic, no independent project or training-unseen claim. Outside-target findings require separate adjudication. Static engines are faster; OCR/tool budgets and scheduling differ.",
        "scoring_is_target_classification_and_discovery": True,
        "billing_cost_not_inferred_from_tokens": True,
    }
    target = OUT / "comparison.json"
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(
        json.dumps(
            {
                "scores": {r["tool"]: r["metrics"]["counts"] for r in rows},
                "paired": report["paired_changes"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
