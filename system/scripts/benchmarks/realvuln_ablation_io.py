"""Offline RealVuln score allocation, compatible-label maps and CSV receipts."""

import csv
import hashlib
import json
import sys

from scripts.benchmarks.realvuln_score import cwes, normalized


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def csv_write(path, rows, display_metrics=False):
    if not rows:
        raise RuntimeError("A required export has no rows")
    if display_metrics:
        rows = [
            {
                **row,
                "ratio_fields_scale": "0_to_1",
                **{
                    f"{key}_100": 100 * float(row[key])
                    for key in ("precision", "recall", "f1", "f3")
                    if row.get(key) not in (None, "")
                },
            }
            for row in rows
        ]
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(
            {
                k: json.dumps(v, ensure_ascii=False)
                if isinstance(v, (list, dict))
                else v
                for k, v in r.items()
            }
            for r in rows
        )


class Evaluator:
    def __init__(self, root):
        sys.path.insert(0, str(root / "evaluator-only"))
        from scorer.matcher import (
            _finding_matches_gt,
            load_ground_truth,
            match_findings,
        )
        from scorer.metrics import compute_scorecard

        self.root = root
        self.load = load_ground_truth
        self.match = match_findings
        self.compatible = _finding_matches_gt
        self.card = compute_scorecard
        self.families = read(root / "evaluator-only/config/cwe-families.json")

    def gold(self, project):
        return self.load(
            str(
                self.root
                / "evaluator-only/ground-truth"
                / project
                / "ground-truth.json"
            )
        )

    def score(self, project, arm, findings, gold):
        matched = self.match(findings, gold)
        card = self.card(project, arm, "2026-10-14", matched, self.families).to_dict()
        allocated, compatible = {}, {}
        for match in matched:
            if match.scanner_finding and match.ground_truth_id:
                allocated.setdefault(match.scanner_finding.finding_id, []).append(
                    match.ground_truth_id
                )
        for finding in findings:
            compatible.setdefault(finding.finding_id, set()).update(
                g["id"] for g in gold["findings"] if self.compatible(finding, g)
            )
        ids = {m.ground_truth_id for m in matched if m.classification == "TP"}
        return card, ids, allocated, {k: sorted(v) for k, v in compatible.items()}


def raw_candidates(static, scout):
    rows = []
    for item in static:
        rows.append(
            {
                "id": item["id"],
                "source": "codeql",
                "location": item["locations"][0],
                "weaknesses": cwes(item["tags"]),
                "description": item["message"],
                "evidence_ids": [],
            }
        )
    for item in scout:
        rows.append({**item, "source": "scout", "weaknesses": [item["weakness"]]})
    return rows


def findings(rows, arm, source):
    return [
        f
        for row in rows
        for f in normalized(
            row["location"],
            row["weaknesses"],
            row["id"],
            row["description"],
            arm,
            source,
        )
    ]


def call_resources(stage):
    records = stage.get("model_calls")
    if records is None:
        return {
            "calls": None,
            "input_tokens": None,
            "output_tokens": None,
            "unknown_usage_calls": None,
        }
    return {
        "calls": len(records),
        "input_tokens": sum(r.get("input_tokens") or 0 for r in records),
        "output_tokens": sum(r.get("output_tokens") or 0 for r in records),
        "unknown_usage_calls": sum(
            r.get("input_tokens") is None or r.get("output_tokens") is None
            for r in records
        ),
    }
