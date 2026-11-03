"""Offline audit of frozen RealVuln results; never invokes scanners or models."""

import argparse
import csv
import hashlib
import json
import re
import statistics
import sys
from collections import Counter
from pathlib import Path
from zipfile import ZipFile


def metrics(rows):
    counts = {
        key: sum(int(row[key]) for row in rows) for key in ("tp", "fp", "fn", "tn")
    }
    tp, fp, fn = (counts[key] for key in ("tp", "fp", "fn"))
    return {
        **counts,
        "precision": tp / (tp + fp) if tp + fp else None,
        "recall": tp / (tp + fn) if tp + fn else None,
        **{
            f"f{beta}": (1 + beta**2) * tp / ((1 + beta**2) * tp + beta**2 * fn + fp)
            if (1 + beta**2) * tp + beta**2 * fn + fp
            else None
            for beta in (1, 3)
        },
    }


def weaknesses(tags):
    found = [re.search(r"cwe[-/]0*(\d+)", tag, re.IGNORECASE) for tag in tags]
    return list(
        dict.fromkeys("CWE-" + str(int(match[1])) for match in found if match)
    ) or ["unknown"]


def normalize(location, cwes, row, scanner, finding_type):
    name, line = location["file"], location["line"]
    if Path(name).is_absolute() or ".." in Path(name).parts or not line:
        raise ValueError(f"Expected a relative, real source location: {location}")
    return [
        finding_type(
            file=name,
            cwe=cwe,
            line=line,
            function=None,
            severity=None,
            rule_id=None,
            message=row.get("description", row.get("message", "")),
            scanner=scanner,
            finding_id=row["id"],
        )
        for cwe in cwes
    ]


def score_project(package, project, finding_type, match, load_gold):
    static = package.read_json(f"receipts/upstream/{project}/static.json")
    scout = package.read_json(f"receipts/upstream/{project}/scout.json")
    assert static["status"] == "succeeded", f"Failed static input: {project}"
    gold = load_gold(
        str(package.root / "evaluator/ground-truth" / project / "ground-truth.json")
    )
    findings = static["rounds"][0]["findings"]
    by_id = {row["id"]: row for row in findings}
    arms = {key: [] for key in "ABCDEF"}
    for row in findings:
        arms["A"].extend(
            normalize(
                row["locations"][0], weaknesses(row["tags"]), row, "A", finding_type
            )
        )
    for row in scout["candidates"]:
        arms["B"].extend(
            normalize(row["location"], [row["weakness"]], row, "B", finding_type)
        )
    arms["C"] = arms["A"] + arms["B"]  # frozen official allocation is order dependent
    states = {}
    for arm in "DEF":
        review = package.read_json(f"receipts/arms/{arm}/system/{project}/review.json")
        assert review["stage"]["status"] == "completed", (arm, project)
        states[arm] = {
            "candidate_states": dict(
                Counter(row["model_assessment"] for row in review["candidates"])
            ),
            "coverage_status": review["stage"]["result"].get("coverage_status"),
        }
        for row in review["candidates"]:
            if row["model_assessment"] != "supported":
                continue
            cwes = [row["weakness"]]
            original = by_id.get(row.get("static_finding_id"))
            if row["weakness"] == "unknown" and original:
                cwes = weaknesses(original["tags"])
            arms[arm].extend(normalize(row["location"], cwes, row, arm, finding_type))
    cards = {}
    for arm, output in arms.items():
        counts = Counter(
            result.classification.lower() for result in match(output, gold)
        )
        cards[arm] = {key: counts[key] for key in ("tp", "fp", "fn", "tn")}
    return cards, states, gold


class Package:
    def __init__(self, root, archive):
        self.root, self.archive = root, archive
        self.zip_fallback_files = set()

    def read_bytes(self, name):
        path = self.root / name
        if path.is_file():
            return path.read_bytes()
        self.zip_fallback_files.add(name)
        return self.archive.read("realvuln-ablation-20261014/" + name)

    def read_json(self, name):
        return json.loads(self.read_bytes(name))

    def verify(self):
        manifest = self.read_json("manifest.json")
        for row in manifest:
            actual = hashlib.sha256(self.read_bytes(row["package_path"])).hexdigest()
            assert actual == row["sha256"], (
                f"Evidence hash mismatch: {row['package_path']}"
            )
        return len(manifest)


def audit(base):
    with ZipFile(base / "realvuln-ablation-20261014-review.zip") as archive:
        package = Package(base / "portable-review", archive)
        verified = package.verify()
        sys.path.insert(0, str(package.root / "evaluator"))
        from parsers import get_parser
        from parsers.base import NormalisedFinding
        from scorer.matcher import load_ground_truth, match_findings

        saved = list(csv.DictReader((base / "ablation-per-project.csv").open()))
        projects = sorted({row["project_id"] for row in saved})
        assert len(projects) == 26 and len(saved) == 156
        expected = {(row["group"], row["project_id"]): row for row in saved}
        per_project, review_states, golds = [], {}, {}
        for project in projects:
            cards, states, golds[project] = score_project(
                package, project, NormalisedFinding, match_findings, load_ground_truth
            )
            for arm, counts in cards.items():
                assert all(
                    counts[key] == int(expected[arm, project][key]) for key in counts
                ), (arm, project, counts)
                per_project.append({"group": arm, "project": project, **counts})
            review_states[project] = states
        formal = package.read_json("formal-summary.json")
        summary = {
            arm: metrics([row for row in per_project if row["group"] == arm])
            for arm in "ABCDEF"
        }
        for row in formal["summary"]:
            actual = summary[row["group"]]
            assert actual["tp"] + actual["fn"] == 676
            for key, value in actual.items():
                assert abs(value - row[key]) < 1e-12, (row["group"], key)
        author = {}
        for scanner in (
            "semgrep",
            "snyk",
            "sonarqube",
            "kolega-v0.0.1",
            "claude-sonnet-4-6-agentic-v1",
            "gemini-3.1-pro-agentic-v1",
        ):
            rows, run_counts, missing = [], [], []
            for project in projects:
                directory = package.root / "evaluator/scan-results" / project / scanner
                files = sorted(
                    path
                    for path in directory.glob("*.json")
                    if not path.name.endswith(".metrics.json")
                )
                if not files:
                    missing.append(project)
                    run_counts.append(0)
                    rows.append(
                        {
                            "project": project,
                            "tp": 0,
                            "fp": 0,
                            "fn": sum(
                                row["is_vulnerable"]
                                for row in golds[project]["findings"]
                            ),
                            "tn": sum(
                                not row["is_vulnerable"]
                                for row in golds[project]["findings"]
                            ),
                        }
                    )
                    continue
                rounds = []
                for path in files:
                    counts = Counter(
                        result.classification.lower()
                        for result in match_findings(
                            get_parser(scanner).parse(str(path)), golds[project]
                        )
                    )
                    rounds.append(
                        {key: counts[key] for key in ("tp", "fp", "fn", "tn")}
                    )
                # Preserve the historical comparison protocol: per-project mean
                # of confusion counts, Python round, then strict micro aggregation.
                rows.append(
                    {
                        "project": project,
                        **{
                            key: round(statistics.mean(row[key] for row in rounds))
                            for key in rounds[0]
                        },
                    }
                )
                run_counts.append(len(rounds))
            author[scanner] = {
                **metrics(rows),
                "projects": len(rows),
                "saved_runs": dict(Counter(run_counts)),
                "missing_output_projects": missing,
                "missing_policy": "Keep full denominator as all-FN; not a successful empty run",
            }
            complete = [row for row in rows if row["project"] not in missing]
            common = {row["project"] for row in complete}
            author[scanner]["common_output_subset"] = {
                "projects": len(common),
                "competitor": metrics(complete),
                "system_F": metrics(
                    [
                        row
                        for row in per_project
                        if row["group"] == "F" and row["project"] in common
                    ]
                ),
                "meaning": "Post-hoc coverage check only; does not replace the frozen full-denominator score",
            }
        identity = package.read_json("formal-review-identity.json")
        stale = json.loads((base / "ablation-data.json").read_text())
        stats = {}
        for arm in "DEF":
            state_counts, coverage = Counter(), Counter()
            for project in projects:
                state_counts.update(review_states[project][arm]["candidate_states"])
                coverage[review_states[project][arm]["coverage_status"]] += 1
            stats[arm] = {
                "candidate_states": dict(state_counts),
                "coverage_states": dict(coverage),
            }
        deltas = []
        for before, after in [("A", "D"), ("B", "E"), ("C", "F"), ("A", "F")]:
            a, b = summary[before], summary[after]
            deltas.append(
                {
                    "comparison": f"{before}->{after}",
                    "tp": b["tp"] - a["tp"],
                    "fp": b["fp"] - a["fp"],
                    **{
                        key + "_pp": 100 * (b[key] - a[key])
                        for key in ("precision", "recall", "f1", "f3")
                    },
                }
            )
        return {
            "checked_on": "2026-11-02",
            "status": "verified",
            "new_model_calls": 0,
            "new_scans": 0,
            "scope": {"projects": 26, "vulnerabilities": 676, "traps": 120},
            "verification": {
                "manifest_files": verified,
                "zip_fallback_files": len(package.zip_fallback_files),
                "project_score_rows": len(per_project),
                "review_stages": len(identity),
                "all_review_policies_verified": all(
                    row["policy_verified"] for row in identity
                ),
            },
            "summary": summary,
            "author_saved_outputs_rescored": author,
            "deltas": deltas,
            "review_states": stats,
            "per_project": per_project,
            "archival_warning": {
                "file": "ablation-data.json",
                "meaning": "Historical interim; use formal-summary.json",
                "old_D_status": stale["summary"][3]["status"],
                "old_F_tp": stale["summary"][-1]["tp"],
            },
            "limits": [
                "Development-exposed data; one run per system arm",
                "Author outputs rescored, competitors not rerun",
                "supported is evidence-gated model output, not human-confirmed",
                "FP means unmatched benchmark output",
                "Source evidence and frozen scans were not re-executed",
                "No claim about accuracy of current deployed CLI commit",
            ],
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.evidence_root.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "status": result["status"],
                "verification": result["verification"],
                "summary": result["summary"],
                "author": result["author_saved_outputs_rescored"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
