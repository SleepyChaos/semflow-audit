"""Evaluator-only official location/CWE matching, with explicit incomplete outputs."""

import argparse
import hashlib
import json
import re
import statistics
import sys
from pathlib import Path

from scripts.benchmarks.realvuln_prepare import save

ARMS = ("codeql", "system_supported", "system_retained", "raw_union")


def read(path):
    return json.loads(path.read_text())


def cwes(tags):
    values = []
    for tag in tags:
        match = re.search(r"cwe[-/]0*(\d+)", tag, re.IGNORECASE)
        if match:
            values.append("CWE-" + str(int(match.group(1))))
    return list(dict.fromkeys(values)) or ["unknown"]


def normalized(location, weaknesses, identifier, message, scanner, source):
    from parsers.base import NormalisedFinding, normalise_path

    name = location.get("file", "")
    path = Path(name)
    if path.is_absolute():
        if not path.resolve().is_relative_to(source.resolve()):
            raise ValueError("Finding refers outside its immutable source")
        name = path.resolve().relative_to(source.resolve()).as_posix()
    line = location.get("line")
    if not name or not line or line < 1:
        raise ValueError("Finding has no real primary source location")
    return [
        NormalisedFinding(
            file=normalise_path(name),
            cwe=cwes([weakness])[0],
            line=line,
            function=None,
            severity=None,
            rule_id=None,
            message=message,
            scanner=scanner,
            finding_id=identifier,
        )
        for weakness in weaknesses
    ]


def project_outputs(output, project, source):
    static_path = output / "static" / project / "result.json"
    baseline = read(static_path) if static_path.exists() else {}
    static = (
        baseline.get("rounds", [{}])[0].get("findings", [])
        if baseline.get("rounds")
        else []
    )
    by_id = {f["id"]: f for f in static}
    system_dir = output / "system" / project
    review = (
        read(system_dir / "review.json")
        if (system_dir / "review.json").exists()
        else {}
    )
    scout = (
        read(system_dir / "scout.json") if (system_dir / "scout.json").exists() else {}
    )
    stages = (
        read(system_dir / "result.json")
        if (system_dir / "result.json").exists()
        else {}
    )
    outputs = {arm: [] for arm in ARMS}

    def static_alert(finding, arm):
        return normalized(
            finding["locations"][0],
            cwes(finding["tags"]),
            finding["id"],
            finding["message"],
            arm,
            source,
        )

    for finding in static:
        for arm in ("codeql", "raw_union"):
            outputs[arm].extend(static_alert(finding, arm))
    for candidate in scout.get("candidates", []):
        outputs["raw_union"].extend(
            normalized(
                candidate["location"],
                [candidate["weakness"]],
                candidate["id"],
                candidate["description"],
                "raw_union",
                source,
            )
        )
    reviewed_static, reviewed_scout = set(), set()
    for candidate in review.get("candidates", []):
        finding_id = candidate.get("static_finding_id")
        source_candidate = candidate.get("related_target")
        if finding_id:
            reviewed_static.add(finding_id)
        if source_candidate:
            reviewed_scout.add(source_candidate)
        assessment = candidate["model_assessment"]
        for arm in ("system_supported", "system_retained"):
            if assessment != "supported" and (
                arm == "system_supported" or assessment == "excluded"
            ):
                continue
            weaknesses = [candidate["weakness"]]
            if candidate["weakness"] == "unknown" and finding_id in by_id:
                weaknesses = cwes(by_id[finding_id]["tags"])
            outputs[arm].extend(
                normalized(
                    candidate["location"],
                    weaknesses,
                    candidate["id"],
                    candidate["description"],
                    arm,
                    source,
                )
            )
    for finding in static:
        if finding["id"] not in reviewed_static:
            outputs["system_retained"].extend(static_alert(finding, "system_retained"))
    for candidate in scout.get("candidates", []):
        if candidate["id"] not in reviewed_scout:
            outputs["system_retained"].extend(
                normalized(
                    candidate["location"],
                    [candidate["weakness"]],
                    candidate["id"],
                    candidate["description"],
                    "system_retained",
                    source,
                )
            )
    return outputs, {
        "static_status": baseline.get("status", "not_evaluated"),
        "system_status": stages.get("status", "not_finished"),
        "static_alerts": len(static),
        "review_candidates": len(review.get("candidates", [])),
        "unresolved_candidates": sum(
            c["model_assessment"] not in {"supported", "excluded"}
            for c in review.get("candidates", [])
        ),
    }


def metrics(rows):
    counts = {key: sum(row[key] for row in rows) for key in ("tp", "fp", "fn", "tn")}
    tp, fp, fn = counts["tp"], counts["fp"], counts["fn"]
    counts.update(
        precision=tp / (tp + fp) if tp + fp else 0,
        recall=tp / (tp + fn) if tp + fn else 0,
    )
    for beta in (1, 2, 3):
        denominator = (1 + beta**2) * tp + beta**2 * fn + fp
        counts[f"f{beta}"] = (1 + beta**2) * tp / denominator if denominator else 0
    return counts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--partial", action="store_true", help="Explicitly label a progress score"
    )
    args = parser.parse_args()
    output = args.output.resolve()
    evaluator = output / "evaluator-only"
    dataset = read(output / "dataset.json")
    finished = all(
        (output / "system" / p / "result.json").exists()
        or (output / "system" / p / "runner-error.json").exists()
        for p in dataset["manifest"]["repos"]
    )
    if not finished and not args.partial:
        raise RuntimeError(
            "Run unfinished; use --partial only for a labeled progress score"
        )
    for relative, expected in dataset["gold_sha256"].items():
        if hashlib.sha256((evaluator / relative).read_bytes()).hexdigest() != expected:
            raise RuntimeError("Evaluator input changed")
    sys.path.insert(0, str(evaluator))
    from parsers import get_parser
    from scorer.matcher import load_ground_truth, match_findings
    from scorer.metrics import compute_scorecard

    families = read(evaluator / "config/cwe-families.json")
    rows = {arm: [] for arm in ARMS}
    author_rows = {
        name: []
        for name in (
            "semgrep",
            "snyk",
            "sonarqube",
            "kolega-v0.0.1",
            "claude-sonnet-4-6-agentic-v1",
            "gemini-3.1-pro-agentic-v1",
        )
    }
    statuses = []
    for project in dataset["manifest"]["repos"]:
        gold = load_ground_truth(
            str(evaluator / "ground-truth" / project / "ground-truth.json")
        )
        source = output / "sources" / project
        outputs, status = project_outputs(output, project, source)
        statuses.append({"project": project, **status})
        for arm in ARMS:
            matches = match_findings(outputs[arm], gold)
            card = compute_scorecard(
                project, arm, "2026-10-13", matches, families
            ).to_dict()
            card["project"] = project
            card["run_status"] = status
            card["normalized_findings"] = [f.__dict__ for f in outputs[arm]]
            rows[arm].append(card)
            save(output / "scores" / project / f"{arm}.json", card)
        for scanner, author_cards in author_rows.items():
            directory = evaluator / "scan-results" / project / scanner
            files = sorted(
                p
                for p in directory.glob("*.json")
                if not p.name.endswith(".metrics.json")
            )
            cards, errors = [], []
            for path in files:
                try:
                    found = get_parser(scanner).parse(str(path))
                    matches = match_findings(found, gold)
                    cards.append(
                        compute_scorecard(
                            project, scanner, "author-output-rescore", matches, families
                        ).to_dict()
                    )
                except Exception as exc:  # noqa: BLE001 - preserve author parse failures
                    errors.append({"file": path.name, "error": str(exc)})
            if cards and not errors:
                # Same rounding of multi-run confusion counts as author's dashboard.
                cell = {
                    key: round(statistics.mean(c[key] for c in cards))
                    for key in ("tp", "fp", "fn", "tn")
                }
            else:
                cell = {
                    "tp": 0,
                    "fp": 0,
                    "fn": sum(f["is_vulnerable"] for f in gold["findings"]),
                    "tn": sum(not f["is_vulnerable"] for f in gold["findings"]),
                }
            author_cards.append(
                {"project": project, **cell, "runs": len(cards), "errors": errors}
            )
    for cards in rows.values():
        counts = metrics(cards)
        if counts["tp"] + counts["fn"] != 676:
            raise RuntimeError("Full paper vulnerability denominator changed")
    summary = {
        "experiment_finished": finished,
        "report_status": "final" if finished else "progress_not_final",
        "dataset": {"projects": 26, "vulnerabilities": 676, "traps": 120},
        "arms": {arm: metrics(cards) for arm, cards in rows.items()},
        "statuses": statuses,
        "author_rescored": {
            name: {
                **metrics(cards),
                "projects_with_outputs": sum(c["runs"] > 0 for c in cards),
            }
            for name, cards in author_rows.items()
        },
        "definition": "Official v1 matcher, exact relative primary file + acceptable CWE + +/-10 lines; each GT consumed once",
        "unknown_cwe_policy": "Retain as unmatched FP instead of silently dropping",
        "failure_policy": "Keep status; no accepted output gives all vulns FN in strict scoring, not a successful empty scan",
        "primary_system": "system_supported: validated AI supported decisions; not independently human confirmed",
        "secondary_system": "system_retained: preserve unknown/unreviewed; drop only validated exclusions",
        "raw_union": "All CodeQL/scout candidates before review; not final system output",
        "paper_comparison": "Same 26 pinned targets and 676 gold entries; GitHub history identity, not verified HF identity",
    }
    save(output / "scores/summary.json", summary)
    save(output / "scores/author-projects.json", author_rows)
    print(
        json.dumps(
            {"arms": summary["arms"], "author_rescored": summary["author_rescored"]},
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
