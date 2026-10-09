"""Evaluator-side scoring and process diagnostics, never fed to the model."""

import argparse
import json
from collections import Counter
from pathlib import Path

from scripts.benchmarks.formal_scoring import score_cases

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "artifacts/research/owasp48/20261007-evolution"


def read(p):
    return json.loads(p.read_text())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", required=True)
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    selection = read(OUT / "samples" / args.sample / "evaluator-selection.json")
    labels = selection["selected"]
    run = OUT / "runs" / args.version / args.sample
    baseline = read(OUT / "static" / args.sample / "result.json")
    scout, review, coverage, batches = [], [], [], []
    usage = Counter()
    for group in selection["model_batches"]:
        path = run / group["group_id"]
        if not (path / "review.json").exists():
            raise RuntimeError("Do not silently score incomplete run")
        s, r = read(path / "scout.json"), read(path / "review.json")
        scout += s["candidates"]
        review += r["candidates"]
        for result in (s, r):
            for key in ("calls", "input_tokens", "output_tokens"):
                usage[key] += result["stage"]["usage"].get(key, 0)
        map_file = ROOT / "artifacts/runs" / s["stage_id"] / "scout-map.json"
        planned = read(map_file)["units"]
        inspected = {u["unit_id"]: u for u in s["stage"]["result"].get("units", [])}
        for file in group["case_paths"]:
            units = [u for u in planned if u["file"] == file]
            actual = [inspected[u["id"]] for u in units if u["id"] in inspected]
            coverage.append(
                {
                    "file": file,
                    "windows": len(units),
                    "inspected": sum(u.get("status") == "inspected" for u in actual),
                    "tasks": dict(
                        Counter(
                            t.get("conclusion", t.get("status"))
                            for u in actual
                            for t in u.get("task_checks", [])
                        )
                    ),
                }
            )
        batches.append(
            {
                "batch": group["group_id"],
                "scout_status": s["stage"]["status"],
                "review_status": r["stage"]["status"],
                "unreviewed": r["stage"]["result"].get("unreviewed_candidate_ids", []),
                "rejected_assessments": [
                    b.get("rejected_assessments", [])
                    for b in r["stage"]["result"].get("batches", [])
                    if b.get("rejected_assessments")
                ],
                "review_incomplete": [
                    b
                    for b in r["stage"]["result"].get("batches", [])
                    if b["status"] == "incomplete"
                ],
                "scout_failures": [
                    u
                    for u in s["stage"]["result"].get("units", [])
                    if u["status"] != "inspected"
                ],
            }
        )
    static = baseline["rounds"][0]["findings"]
    supported = [c for c in review if c["model_assessment"] == "supported"]
    modes = {
        "CodeQL": static,
        "Scout_raw": scout,
        "Union_raw": static + scout,
        "Platform_supported": supported,
    }
    scores = {name: score_cases(labels, findings) for name, findings in modes.items()}
    predictions = {
        k: {r["task_id"] for r in value["cases"] if r["predicted"]}
        for k, value in scores.items()
    }
    positives = {r["task_id"] for r in labels if r["vulnerable"]}
    negatives = {r["task_id"] for r in labels if not r["vulnerable"]}
    transitions = {
        "added_TP_over_CodeQL": sorted(
            (predictions["Platform_supported"] - predictions["CodeQL"]) & positives
        ),
        "lost_TP_from_CodeQL": sorted(
            (predictions["CodeQL"] - predictions["Platform_supported"]) & positives
        ),
        "lost_TP_from_union": sorted(
            (predictions["Union_raw"] - predictions["Platform_supported"]) & positives
        ),
        "removed_FP_from_union": sorted(
            (predictions["Union_raw"] - predictions["Platform_supported"]) & negatives
        ),
    }
    by_file = {r["file"]: r for r in labels}
    diagnostics = []
    for row in scores["Platform_supported"]["cases"]:
        if row["classification"] not in {"FN", "FP"}:
            continue
        file = row["file"]
        diagnostics.append(
            {
                "label": row,
                "scout": [c for c in scout if c["location"].get("file") == file],
                "review": [c for c in review if c["location"].get("file") == file],
            }
        )
    alt = [
        {
            "id": c["id"],
            "file": c["location"].get("file"),
            "weakness": c["weakness"],
            "intended_CWE": by_file[c["location"]["file"]]["cwe"],
            "verdict": c["model_assessment"],
            "title": c["title"],
        }
        for c in review
        if c["location"].get("file") in by_file
        and c["weakness"] != "CWE-" + str(by_file[c["location"]["file"]]["cwe"])
    ]
    result = {
        "sample": args.sample,
        "version": args.version,
        "case_count": 48,
        "scores": scores,
        "usage": dict(usage),
        "parallel_wall_seconds": read(run / "summary.json")["parallel_wall_seconds"],
        "static_seconds_once": baseline["wall_seconds"],
        "verdict_counts": dict(Counter(c["model_assessment"] for c in review)),
        "unreviewed": sum(
            c["model_assessment"] in {"pending", "unknown"} for c in review
        ),
        "coverage": coverage,
        "batches": batches,
        "transitions": transitions,
        "errors": diagnostics,
        "alternate_CWE_not_auto_adjudicated": alt,
        "official_scorecard": False,
        "independent_unseen_project": False,
    }
    (run / "evaluation.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2)
    )
    print(
        json.dumps(
            {
                "sample": args.sample,
                "version": args.version,
                "scores": {
                    k: {
                        metric: v[metric]
                        for metric in ("counts", "precision", "recall", "f1")
                    }
                    for k, v in scores.items()
                },
                "usage": result["usage"],
                "unreviewed": result["unreviewed"],
                "incomplete_cases": sum(
                    c["windows"] != c["inspected"] for c in coverage
                ),
                "wall": result["parallel_wall_seconds"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
