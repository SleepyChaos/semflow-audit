"""Post-run evaluator only: exact frozen testcase/CWE oracle, no feedback to model."""

import json
from collections import Counter
from pathlib import Path

from scripts.benchmarks.formal_scoring import score_cases

ROOT = Path(__file__).resolve().parents[2]
PREP = ROOT / "artifacts/research/owasp-discovery/20261007-pilot-preparation"
RUN = ROOT / "artifacts/research/owasp-discovery/20261007-pilot-v1"
STATIC = (
    ROOT
    / "artifacts/research/formal/20261005-calibration-v1/static/owasp-python-loader-fixed/result.json"
)
GOLD = (
    ROOT
    / "benchmarks/evaluator-only/experiments/20261005-calibration-v1/owasp-labels.json"
)


def read(p):
    return json.loads(p.read_text())


def main():
    selection = read(PREP / "evaluator-selection.json")
    labels = selection["selected"]
    baseline = read(STATIC)["rounds"][0]["findings"]
    scout, verified, review_all, coverage = [], [], [], []
    batch_status = []
    usage = Counter()
    stage_seconds = 0
    for batch in selection["model_batches"]:
        path = RUN / batch["group_id"]
        s, r = read(path / "scout.json"), read(path / "review.json")
        scout += s["candidates"]
        review_all += r["candidates"]
        verified += [c for c in r["candidates"] if c["model_assessment"] == "supported"]
        batch_status.append(
            {
                "batch": batch["group_id"],
                "scout_status": s["stage"]["status"],
                "review_status": r["stage"]["status"],
                "scout_seconds": s["wall_seconds"],
                "review_seconds": r["wall_seconds"],
                "unreviewed": len(
                    r["stage"]["result"].get("unreviewed_candidate_ids", [])
                ),
                "rejections": [
                    b.get("rejected_assessments", [])
                    for b in r["stage"]["result"].get("batches", [])
                    if b.get("rejected_assessments")
                ],
            }
        )
        units = s["stage"]["result"].get("units", [])
        for case in batch["case_paths"]:
            map_file = ROOT / "artifacts/runs" / s["stage_id"] / "scout-map.json"
            scheduled = [u for u in read(map_file)["units"] if u["file"] == case]
            result_by_id = {u["unit_id"]: u for u in units}
            inspected = [
                result_by_id[u["id"]]
                for u in scheduled
                if result_by_id.get(u["id"], {}).get("status") == "inspected"
            ]
            related = [c for c in r["candidates"] if c["location"].get("file") == case]
            coverage.append(
                {
                    "file": case,
                    "scheduled_windows": len(scheduled),
                    "inspected_windows": len(inspected),
                    "task_statuses": dict(
                        Counter(
                            t["status"]
                            for u in inspected
                            for t in u.get("task_checks", [])
                        )
                    ),
                    "review_verdicts": dict(
                        Counter(c["model_assessment"] for c in related)
                    ),
                    "source_incomplete": len(inspected) != len(scheduled)
                    or not scheduled,
                }
            )
        for output in (s, r):
            usage.update(output["stage"]["usage"])
            stage_seconds += output["wall_seconds"]
    modes = {
        "D0_CodeQL": baseline,
        "D1_scout_unverified": scout,
        "D2_union_unverified": baseline + scout,
        "D3_supported_review": verified,
    }
    scores = {}
    for name, findings in modes.items():
        overall = score_cases(labels, findings)
        per_category = {
            cat: score_cases([l for l in labels if l["category"] == cat], findings)
            for cat in sorted({l["category"] for l in labels})
        }
        scores[name] = {"overall": overall, "per_category": per_category}
    predictions = {
        name: {r["task_id"] for r in score["overall"]["cases"] if r["predicted"]}
        for name, score in scores.items()
    }
    positives = {l["task_id"] for l in labels if l["vulnerable"]}
    negatives = {l["task_id"] for l in labels if not l["vulnerable"]}
    transitions = {
        "D1_extra_TP_over_D0": sorted(
            (predictions["D1_scout_unverified"] - predictions["D0_CodeQL"]) & positives
        ),
        "D3_extra_TP_over_D0": sorted(
            (predictions["D3_supported_review"] - predictions["D0_CodeQL"]) & positives
        ),
        "D3_lost_TP_from_D0": sorted(
            (predictions["D0_CodeQL"] - predictions["D3_supported_review"]) & positives
        ),
        "D3_lost_TP_from_union": sorted(
            (predictions["D2_union_unverified"] - predictions["D3_supported_review"])
            & positives
        ),
        "D3_removed_FP_from_union": sorted(
            (predictions["D2_union_unverified"] - predictions["D3_supported_review"])
            & negatives
        ),
    }
    by_file = {l["file"]: l for l in labels}
    alternate = [
        {
            "candidate_id": c["id"],
            "file": c["location"]["file"],
            "weakness": c["weakness"],
            "intended_CWE": by_file[c["location"]["file"]]["cwe"],
            "assessment": c["model_assessment"],
        }
        for c in review_all
        if c["location"].get("file") in by_file
        and c["weakness"] != "CWE-" + str(by_file[c["location"]["file"]]["cwe"])
    ]
    report = {
        "scope": "56 representative cases, 28 positive/28 negative; AI not full 1230",
        "official_scorecard": False,
        "formal_paper_result": False,
        "selection_seed": selection["seed"],
        "scores": scores,
        "full_static_1230": score_cases(read(GOLD), baseline),
        "transitions": transitions,
        "alternate_CWE_candidates_not_auto_scored": alternate,
        "coverage": coverage,
        "batches": batch_status,
        "model_usage": dict(usage),
        "actual_parallel_wall_seconds": read(RUN / "summary.json")[
            "actual_parallel_wall_seconds"
        ],
        "cached_full_static_original_seconds": read(STATIC)["wall_seconds"],
        "source_incomplete_cases": sum(c["source_incomplete"] for c in coverage),
        "summed_stage_seconds_not_parallel_wall": stage_seconds,
        "review_verdict_counts": dict(
            Counter(c["model_assessment"] for c in review_all)
        ),
        "unreviewed": sum(
            c["model_assessment"] in {"unknown", "pending"} for c in review_all
        ),
        "limitations": [
            "Exact file plus intended CWE, no posthoc CWE equivalence remapping.",
            "Absent positive predictions on failed/unknown inspections count as operational misses; TN is not certified safe.",
            "D0 uses cached full snapshot analysis; AI uses scoped cases plus helpers; not equal-input/cost comparison.",
            "Outside-target and alternate-CWE findings require separate adjudication, not automatically false alarms.",
            "Public synthetic materials; no training-unseen or runtime exploitation claim.",
            "One run per configuration, not repeated statistically significant paper uplift.",
        ],
    }
    (RUN / "evaluation.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2)
    )
    print(
        json.dumps(
            {
                "scores": {k: v["overall"]["counts"] for k, v in scores.items()},
                "usage": dict(usage),
                "unreviewed": report["unreviewed"],
                "source_incomplete_cases": sum(
                    c["source_incomplete"] for c in coverage
                ),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
