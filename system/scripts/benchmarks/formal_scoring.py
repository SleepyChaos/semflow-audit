"""Explicit OWASP testcase/CWE adapter, separate from natural-root adjudication."""

import re
from pathlib import PurePosixPath


def score_cases(labels, findings):
    predictions = set()
    outside = []
    files = {PurePosixPath(row["file"]).name: row for row in labels}
    for finding in findings:
        cwes = {
            int(match.group(1))
            for tag in finding.get("tags", [])
            if (match := re.search(r"cwe[-/](\d+)$", tag, re.IGNORECASE))
        }
        weakness = finding.get("weakness", "")
        if match := re.fullmatch(r"CWE-(\d+)", weakness):
            cwes.add(int(match.group(1)))
        matched = False
        for location in finding.get("locations", [finding.get("location", {})]):
            label = files.get(PurePosixPath(location.get("file", "")).name)
            if label and label["cwe"] in cwes:
                predictions.add(label["task_id"])
                matched = True
        if not matched:
            outside.append(finding.get("id"))
    counts = {key: 0 for key in ("TP", "FP", "TN", "FN")}
    rows = []
    for label in labels:
        predicted = label["task_id"] in predictions
        classification = (
            ("TP" if predicted else "FN")
            if label["vulnerable"]
            else ("FP" if predicted else "TN")
        )
        counts[classification] += 1
        rows.append({**label, "predicted": predicted, "classification": classification})
    tp, fp, tn, fn = (counts[k] for k in ("TP", "FP", "TN", "FN"))
    return {
        "scope": "primary_location_and_exact_CWE_testcase_adapter_not_official_scorecard",
        "counts": counts,
        "precision": tp / (tp + fp) if tp + fp else None,
        "recall": tp / (tp + fn) if tp + fn else None,
        "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None,
        "false_positive_rate": fp / (fp + tn) if fp + tn else None,
        "outside_target_alerts": outside,
        "cases": rows,
    }
