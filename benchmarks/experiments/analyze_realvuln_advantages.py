"""Locate project/CWE advantages in frozen results; no model or scanner execution."""

import argparse
import csv
import json
import statistics
import sys
from collections import Counter
from pathlib import Path
from zipfile import ZipFile

from verify_realvuln_snapshot import Package, metrics

SCANNERS = (
    "semgrep",
    "snyk",
    "sonarqube",
    "kolega-v0.0.1",
    "claude-sonnet-4-6-agentic-v1",
    "gemini-3.1-pro-agentic-v1",
)


def read_csv(path):
    with path.open() as stream:
        return list(csv.DictReader(stream))


def write_csv(path, rows):
    with path.open("w") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def author_scores(root, project, scanner, gold, parser, matcher):
    paths = sorted(
        path
        for path in (root / "evaluator/scan-results" / project / scanner).glob("*.json")
        if not path.name.endswith(".metrics.json")
    )
    if not paths:
        return None
    rounds, union = [], set()
    for path in paths:
        matches = matcher(parser(scanner).parse(str(path)), gold)
        counts = Counter(row.classification.lower() for row in matches)
        rounds.append({key: counts[key] for key in ("tp", "fp", "fn", "tn")})
        union.update(
            row.ground_truth_id for row in matches if row.classification == "TP"
        )
    counts = {
        key: round(statistics.mean(row[key] for row in rounds)) for key in rounds[0]
    }
    return {"runs": len(paths), "gold_union": union, **metrics([counts])}


def analyze(base, output):
    rows = read_csv(base / "ablation-per-project.csv")
    by = {(row["group"], row["project_id"]): row for row in rows}
    projects = sorted({row["project_id"] for row in rows})
    overlap = {
        (row["project_id"], row["gold_id"]): row
        for row in read_csv(base / "discovery-overlap.csv")
    }
    transitions = {
        (row["project_id"], row["gold_id"]): row
        for row in read_csv(base / "review-gold-transitions.csv")
        if row["group"] == "F"
    }
    assert len(projects) == 26 and len(transitions) == 676
    project_rows, gain_rows, external_rows = [], [], []
    cwe_counts, class_counts = Counter(), Counter()
    stats = Counter()
    with ZipFile(base / "realvuln-ablation-20261014-review.zip") as archive:
        package = Package(base / "portable-review", archive)
        verified_files = package.verify()
        sys.path.insert(0, str(package.root / "evaluator"))
        from parsers import get_parser
        from scorer.matcher import load_ground_truth, match_findings

        for project in projects:
            gold = load_ground_truth(
                str(
                    package.root
                    / "evaluator/ground-truth"
                    / project
                    / "ground-truth.json"
                )
            )
            gold_by_id = {
                row["id"]: row for row in gold["findings"] if row["is_vulnerable"]
            }
            f_hits = {
                key
                for key in gold_by_id
                if transitions[project, key]["after_supported_hit"] == "True"
            }
            a_hits = {
                key
                for key in gold_by_id
                if overlap[project, key]["codeql_independent_hit"] == "True"
            }
            b_hits = {
                key
                for key in gold_by_id
                if overlap[project, key]["scout_independent_hit"] == "True"
            }
            gains, lost = f_hits - a_hits, a_hits - f_hits
            assert len(f_hits) == int(by["F", project]["tp"])
            assert len(a_hits) == int(by["A", project]["tp"])
            stats.update(
                {
                    "gained_vs_CodeQL": len(gains),
                    "lost_CodeQL": len(lost),
                    "retained_CodeQL": len(f_hits & a_hits),
                }
            )
            f = by["F", project]
            row = {
                "project": project,
                "gold": len(gold_by_id),
                **{f"{g}_tp": int(by[g, project]["tp"]) for g in "ABCDEF"},
                "F_fp": int(f["fp"]),
                "F_precision": float(f["precision"]),
                "F_recall": float(f["recall"]),
                "tp_net_vs_CodeQL": len(f_hits) - len(a_hits),
                "added_vs_CodeQL": len(gains),
                "lost_CodeQL": len(lost),
                "added_also_in_Scout": len(gains & b_hits),
                "C_to_F_lost": sum(
                    transitions[project, key]["transition"] == "lost_from_supported"
                    for key in gold_by_id
                ),
                "C_to_F_gained": sum(
                    transitions[project, key]["transition"] == "gained_after_review"
                    for key in gold_by_id
                ),
            }
            authors = {}
            for scanner in SCANNERS:
                score = author_scores(
                    package.root, project, scanner, gold, get_parser, match_findings
                )
                authors[scanner] = score
                external_rows.append(
                    {
                        "project": project,
                        "scanner": scanner,
                        "saved_runs": score["runs"] if score else 0,
                        "system_tp": len(f_hits),
                        "author_tp_rounded_mean": score["tp"] if score else None,
                        "tp_difference": len(f_hits) - score["tp"] if score else None,
                        "system_gold_missed_in_all_saved_runs": len(
                            f_hits - score["gold_union"]
                        )
                        if score
                        else None,
                        "system_fp": int(f["fp"]),
                        "author_fp_rounded_mean": score["fp"] if score else None,
                    }
                )
                prefix = scanner.split("-")[0]
                row[prefix + "_tp"] = score["tp"] if score else None
                row[prefix + "_saved_runs"] = score["runs"] if score else 0
            project_rows.append(row)
            for key in sorted(gains):
                label, transition = gold_by_id[key], transitions[project, key]
                cwe_counts[label["primary_cwe"]] += 1
                class_counts[label.get("vulnerability_class", "unspecified")] += 1
                gain_rows.append(
                    {
                        "project": project,
                        "gold_id": key,
                        "primary_cwe": label["primary_cwe"],
                        "vulnerability_class": label.get("vulnerability_class"),
                        "file": label.get("file"),
                        "line_start": label.get("location", {}).get("start_line"),
                        "line_end": label.get("location", {}).get("end_line"),
                        "also_in_independent_Scout": key in b_hits,
                        "candidate_ids": transition["candidate_ids"],
                        "review_reason": transition["reasons"],
                        **{
                            scanner + "_all_saved_runs_missed": None
                            if authors[scanner] is None
                            else key not in authors[scanner]["gold_union"]
                            for scanner in SCANNERS
                        },
                    }
                )
    assert stats["gained_vs_CodeQL"] == 252 and stats["lost_CodeQL"] == 4
    assert sum(cwe_counts.values()) == 252
    output.mkdir(parents=True, exist_ok=True)
    project_rows.sort(key=lambda row: row["tp_net_vs_CodeQL"], reverse=True)
    write_csv(output / "project-advantages.csv", project_rows)
    write_csv(output / "external-project-comparison.csv", external_rows)
    write_csv(output / "added-gold-cases.csv", gain_rows)
    cwes = [
        {"cwe": key, "added_vs_CodeQL": value}
        for key, value in cwe_counts.most_common()
    ]
    write_csv(output / "added-cwes.csv", cwes)
    result = {
        "checked_on": "2026-11-02",
        "verified_manifest_files": verified_files,
        "scope": "Post-hoc diagnosis of development-exposed frozen data; no novelty or causality proof",
        "stats": dict(stats),
        "projects": project_rows,
        "added_cwes": cwes,
        "added_vulnerability_classes": dict(class_counts.most_common()),
        "comparator_policy": "Author saved runs: per-project confusion-count mean rounded; missed-in-all uses union of saved gold hits; missing output is unknown, not zero",
    }
    (output / "advantage-summary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    analyze(args.evidence_root.resolve(), args.output.resolve())


if __name__ == "__main__":
    main()
