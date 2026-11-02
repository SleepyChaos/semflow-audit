"""Diagnose frozen discovery/review cohorts offline; never infer semantic truth."""

import argparse
import csv
import io
import json
import sys
from collections import Counter
from pathlib import Path
from zipfile import ZipFile

from analyze_realvuln_advantages import write_csv
from verify_realvuln_snapshot import Package, normalize, weaknesses


def table(package, name):
    return list(csv.DictReader(io.StringIO(package.read_bytes(name).decode())))


def complementarity(package, overlap):
    from parsers.base import NormalisedFinding
    from scorer.matcher import _finding_matches_gt, load_ground_truth

    result = []
    for project in sorted({r["project_id"] for r in overlap}):
        static = package.read_json(f"receipts/upstream/{project}/static.json")
        if static["status"] != "succeeded":
            raise ValueError(f"Static analysis did not succeed: {project}")
        labels = load_ground_truth(
            str(package.root / "evaluator/ground-truth" / project / "ground-truth.json")
        )
        gold = {r["id"]: r for r in labels["findings"]}
        alerts = static["rounds"][0]["findings"]
        for row in overlap:
            if row["project_id"] != project or not (
                row["scout_independent_hit"] == "True"
                and row["codeql_independent_hit"] == "False"
            ):
                continue
            label = gold[row["gold_id"]]
            nearby = []
            for alert in alerts:
                # Relax CWE only, keeping the frozen official location matcher.
                finding = normalize(
                    alert["locations"][0],
                    label["acceptable_cwes"][:1],
                    alert,
                    "diagnostic",
                    NormalisedFinding,
                )[0]
                if _finding_matches_gt(finding, label):
                    nearby.append(
                        {"id": alert["id"], "cwes": weaknesses(alert["tags"])}
                    )
            compatible = json.loads(row["codeql_compatible_candidates"])
            signal = (
                "compatible_but_not_allocated"
                if compatible
                else "nearby_static_different_cwe"
                if nearby
                else "no_nearby_static_output"
            )
            result.append(
                {
                    "project_id": project,
                    "gold_id": row["gold_id"],
                    "primary_cwe": label["primary_cwe"],
                    "file": label["file"],
                    "location": label["location"],
                    "scout_ids": row["scout_compatible_candidates"],
                    "static_compatible_ids": compatible,
                    "nearby_static": nearby,
                    "observed_signal": signal,
                    "rule_coverage": "unadjudicated",
                    "semantic_reasoning": "unadjudicated",
                    "extracted_input_coverage": "unverified",
                    "interpretation": "Location/CWE signal only; not a causal explanation or new root count",
                }
            )
    return result


def review_cohort(package, identities, transitions):
    rows, project_rows = [], []
    by_transition = {
        (r["project_id"], r["review_candidate_id"]): r
        for r in transitions
        if r["group"] == "F"
    }
    for identity in identities:
        if identity["group"] != "F":
            continue
        project = identity["project_id"]
        review = package.read_json(f"receipts/arms/F/system/{project}/review.json")
        stage = review["stage"]
        assessments = {}
        for batch in stage["result"]["batches"]:
            for assessment in batch.get("assessments", []):
                assessments[assessment["candidate_id"]] = (assessment, batch)
        recovery = set(stage["result"].get("recovery_attempted_ids", []))
        start = len(rows)
        for candidate in review["candidates"]:
            identifier = candidate["id"]
            assessment, batch = assessments.get(identifier, ({}, {}))
            missing = [
                p["premise"]
                for p in assessment.get("premises", [])
                if p["status"] == "missing"
            ]
            transition = by_transition.get((project, identifier), {})
            rows.append(
                {
                    "project_id": project,
                    "stage_id": stage["id"],
                    "candidate_id": identifier,
                    "state": candidate["model_assessment"],
                    "security_property": assessment.get("security_property", "unknown"),
                    "missing_roles": missing,
                    "missing_premises": assessment.get("missing_premises", []),
                    "batch_id": batch.get("batch_id"),
                    "batch_status": batch.get("status"),
                    "batch_tool_observations": len(batch.get("trace", [])),
                    "recovery_attempted": identifier in recovery,
                    "before_gold_ids": transition.get(
                        "before_allocated_gold_ids", "[]"
                    ),
                    "after_gold_ids": transition.get(
                        "after_supported_allocated_gold_ids", "[]"
                    ),
                    "classification_changed": transition.get("cwe_changed", "unknown"),
                    "location_changed": transition.get("location_changed", "unknown"),
                    "interpretation": "Batch-level trace is not proof of candidate-specific evidence use",
                }
            )
        subset = rows[start:]
        project_rows.append(
            {
                "project_id": project,
                "stage_id": stage["id"],
                "stage_status": stage["status"],
                "coverage_status": stage["result"].get("coverage_status"),
                **{
                    s: sum(r["state"] == s for r in subset)
                    for s in ("supported", "insufficient", "excluded", "unknown")
                },
                "insufficient_with_missing_roles": sum(
                    r["state"] == "insufficient" and bool(r["missing_roles"])
                    for r in subset
                ),
                "insufficient_recovery_attempted": sum(
                    r["state"] == "insufficient" and r["recovery_attempted"]
                    for r in subset
                ),
            }
        )
    return rows, project_rows


def encoded_rows(rows):
    return [
        {
            k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v
            for k, v in row.items()
        }
        for row in rows
    ]


def run(base, output):
    with ZipFile(base / "realvuln-ablation-20261014-review.zip") as archive:
        package = Package(base / "portable-review", archive)
        verified = package.verify()
        sys.path.insert(0, str(package.root / "evaluator"))
        overlap = table(package, "discovery-overlap.csv")
        identities = package.read_json("formal-review-identity.json")
        complement = complementarity(package, overlap)
        reviews, projects = review_cohort(
            package, identities, table(package, "review-transitions.csv")
        )
        gold_transitions = [
            r
            for r in table(package, "review-gold-transitions.csv")
            if r["group"] == "F"
        ]
        membership = Counter(
            (
                r["codeql_independent_hit"] == "True",
                r["scout_independent_hit"] == "True",
            )
            for r in overlap
        )
        insufficient = [r for r in reviews if r["state"] == "insufficient"]
        summary = {
            "mode": "offline_retrospective_no_model_or_scanner_calls",
            "verified_package_files": verified,
            "independent_discovery": {
                "both": membership[True, True],
                "static_only": membership[True, False],
                "scout_only": membership[False, True],
                "neither": membership[False, False],
                "scout_only_location_cwe_signals": dict(
                    Counter(r["observed_signal"] for r in complement)
                ),
                "causal_attribution": "unadjudicated; no rule/input/semantic explanation inferred",
            },
            "F_review": {
                "projects": len(projects),
                "candidates": len(reviews),
                "states": dict(Counter(r["state"] for r in reviews)),
                "insufficient_missing_role_patterns": dict(
                    Counter(
                        "+".join(sorted(r["missing_roles"])) or "no_structured_missing"
                        for r in insufficient
                    )
                ),
                "insufficient_with_batch_reads": sum(
                    r["batch_tool_observations"] > 0 for r in insufficient
                ),
                "insufficient_with_recovery_attempt": sum(
                    r["recovery_attempted"] for r in insufficient
                ),
                "projects_with_insufficient": sum(
                    p["insufficient"] > 0 for p in projects
                ),
                "gold_transitions": dict(
                    Counter(r["transition"] for r in gold_transitions)
                ),
            },
            "limits": [
                "Missing roles are model-declared, not independently established evidence gaps",
                "No citation usage/reasoning error inferred without saved request and source content",
                "Unmatched outputs are not independently confirmed false positives",
                "Insufficient is unresolved; a recovery attempt may precede the final insufficient state",
            ],
        }
    output.mkdir(parents=True, exist_ok=True)
    for name, rows in [
        ("complementarity-cases.csv", complement),
        ("review-candidates.csv", reviews),
        ("review-projects.csv", projects),
    ]:
        write_csv(output / name, encoded_rows(rows))
    (output / "cohort-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.evidence_root.resolve(), args.output.resolve())


if __name__ == "__main__":
    main()
