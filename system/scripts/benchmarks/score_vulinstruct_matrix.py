"""Offline metrics from independently adjudicated root causes and actual receipts.

Annotations are kept outside the detector and the knowledge corpus.
"""

import argparse
import json
from collections import Counter
from pathlib import Path
from uuid import UUID

from semflow_research.public.runs import inspect


def metrics(positives, negatives, predicted, decided_negative):
    tp = len(positives & predicted)
    fp = len(negatives & predicted)
    fn = len(positives - predicted)
    tn = len(negatives & decided_negative)
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    denominator = 2 * tp + fp + fn
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": precision,
        "recall": recall,
        "f1": 2 * tp / denominator if denominator and precision is not None else None,
        "undecided_controls": len(negatives - predicted - decided_negative),
    }


def score_arm(truth, group, *, with_review):
    if not truth or any(type(value) is not bool for value in truth.values()):
        raise ValueError("Root cause truth values must be booleans")
    positives = {key for key, value in truth.items() if value}
    negatives = set(truth) - positives
    reviewed = group.get("review", {})
    detections = group["detected"]
    checked = set(group["inspected"])
    if not (set(detections) | checked | set(reviewed)) <= truth.keys():
        raise ValueError("Adjudication refers to an undeclared root")
    if not set(reviewed) <= detections.keys():
        raise ValueError("A review decision needs an original candidate match")
    if not set(reviewed.values()) <= {
        "supported",
        "refuted",
        "insufficient",
        "unreviewed",
    }:
        raise ValueError("Unexpected source review status")
    origins = {"codeql", "scout", "specification_guided"}
    if any(not flags or not set(flags) <= origins for flags in detections.values()):
        raise ValueError("Each match needs a real discovery origin")
    found = set(detections)
    counts = {
        "discovery": metrics(positives, negatives, found, checked - found),
        "positive_roots_not_inspected": len(positives - checked - found),
        "inspected_positives_without_candidate": len((positives & checked) - found),
        "discovery_origin_intersections": dict(
            Counter("|".join(sorted(set(flags))) for flags in detections.values())
        ),
        "guidance_only_true_roots": sum(
            set(detections[key]) == {"specification_guided"}
            for key in positives & found
        ),
        "review": None,
    }
    if with_review:
        supported = {
            root for root, verdict in reviewed.items() if verdict == "supported"
        }
        refuted = {root for root, verdict in reviewed.items() if verdict == "refuted"}
        insufficient = {
            root for root, verdict in reviewed.items() if verdict == "insufficient"
        }
        counts["review"] = {
            **metrics(positives, negatives, supported, refuted | (checked - found)),
            "conclusions": dict(Counter(reviewed.values())),
            "false_exclusions": len(positives & refuted),
            "true_roots_insufficient": len(positives & insufficient),
            "unreviewed_candidates": len(found - supported - refuted - insufficient),
            "confirmation_rate": len(supported) / len(found) if found else None,
        }
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--adjudications", type=Path, required=True)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_bytes())
    adjudications = json.loads(args.adjudications.read_bytes())
    results = {}
    for arm, spec in plan["specs"].items():
        receipt = inspect(UUID(spec["execution_id"]), root=args.root, missing_ok=True)
        group = adjudications["arms"].get(arm)
        row = {
            "execution_status": receipt.execution_status if receipt else "not_run",
            "metrics": None,
        }
        if receipt:
            row["usage"] = receipt.usage.model_dump(mode="json")
        if (
            receipt
            and receipt.execution_status == "completed"
            and receipt.result
            and group
        ):
            if spec["model"]["provider"] == "scripted-test":
                row["execution_status"] = "scripted"
            else:
                row["metrics"] = score_arm(
                    adjudications["truth"], group, with_review=arm in {"E", "F"}
                )
        results[arm] = row
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
