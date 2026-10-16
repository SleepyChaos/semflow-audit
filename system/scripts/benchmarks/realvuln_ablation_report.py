"""Score independent review arms and export progress without inventing failures."""

import argparse
from collections import Counter
from pathlib import Path

from scripts.benchmarks.realvuln_ablation_diagnostics import discovery_metadata
from scripts.benchmarks.realvuln_ablation_io import (
    Evaluator,
    call_resources,
    csv_write,
    findings,
    raw_candidates,
    read,
)
from scripts.benchmarks.realvuln_ablation_transitions import transitions
from scripts.benchmarks.realvuln_prepare import save
from scripts.benchmarks.realvuln_score import cwes, metrics


def review_outputs(review, static):
    by_id = {r["id"]: r for r in static}
    output = []
    for candidate in review["candidates"]:
        if candidate["model_assessment"] != "supported":
            continue
        weaknesses = [candidate["weakness"]]
        finding = by_id.get(candidate.get("static_finding_id"))
        if candidate["weakness"] == "unknown" and finding:
            weaknesses = cwes(finding["tags"])
        output.append({**candidate, "weaknesses": weaknesses})
    return output


def report(base, output):
    origins = read(base / "20261013-progress-v3-retest/incremental-report-data.json")[
        "provenance"
    ]
    history = output / "historical-incremental"
    import csv

    per = [
        r
        for r in csv.DictReader((history / "ablation-per-project.csv").open())
        if r["group"] in {"A", "B", "C"}
    ]
    discovery_rows = {(r["group"], r["project_id"]): r for r in per}
    historical = read(history / "ablation-data.json")
    summary = [r for r in historical["summary"] if r["group"] in {"A", "B", "C"}]
    discovery_metadata(per, summary, origins)
    evaluator = Evaluator(base / "20261013-progress-v2")
    all_transitions, gold_transitions, cards = [], [], {g: [] for g in "DEF"}
    resource_rows, stage_ids = [], set()
    for group in "DEF":
        for project, location in origins.items():
            origin = Path(location)
            directory = output / "arms" / group / "system" / project
            path = directory / "review.json"
            if not path.exists():
                per.append(
                    {
                        "group": group,
                        "project_id": project,
                        "status": "running_or_not_started",
                        "gold_vulnerabilities": read(
                            origin / "scores" / project / "codeql.json"
                        )["tp"]
                        + read(origin / "scores" / project / "codeql.json")["fn"],
                    }
                )
                continue
            review = read(path)
            static = read(origin / "static" / project / "result.json")["rounds"][0][
                "findings"
            ]
            scout_record = read(origin / "system" / project / "scout.json")
            scout = scout_record["candidates"]
            coverage = scout_record["stage"]["result"].get("coverage", {})
            raw = raw_candidates(
                static if group in {"D", "F"} else [],
                scout if group in {"E", "F"} else [],
            )
            registration = directory / "input.json"
            if registration.exists():
                mapping = read(registration)["source_candidate_mapping"]
                for candidate in raw:
                    if candidate["source"] == "scout":
                        candidate["original_candidate_id"] = candidate["id"]
                        candidate["id"] = mapping[candidate["id"]]
            source, gold = origin / "sources" / project, evaluator.gold(project)
            before = evaluator.score(
                project, group + "-before", findings(raw, group, source), gold
            )
            after = evaluator.score(
                project,
                group,
                findings(review_outputs(review, static), group, source),
                gold,
            )
            cards[group].append(after[0])
            details = transitions(
                project,
                origin,
                raw,
                review,
                {"C": before, "F": after},
                evaluator,
                gold,
                source,
            )
            for row in details:
                row.update(group=group, receipt=str(path))
            all_transitions.extend(details)
            for label in gold["findings"]:
                if not label["is_vulnerable"]:
                    continue
                identifier = label["id"]
                related = [
                    r
                    for r in details
                    if identifier in r.get("before_compatible_gold_ids", [])
                ]
                gold_transitions.append(
                    {
                        "group": group,
                        "project_id": project,
                        "gold_id": identifier,
                        "before_hit": identifier in before[1],
                        "after_supported_hit": identifier in after[1],
                        "transition": "retained"
                        if identifier in before[1] & after[1]
                        else "lost_from_supported"
                        if identifier in before[1]
                        else "gained_after_review"
                        if identifier in after[1]
                        else "missed_both",
                        "related_candidate_states": dict(
                            Counter(r["review_state"] for r in related)
                        ),
                        "candidate_ids": [r["candidate_id"] for r in related],
                        "reasons": [
                            r.get("reason") for r in related if r.get("reason")
                        ],
                        "scoring_change_possible": any(
                            r.get("cwe_changed") or r.get("location_changed")
                            for r in related
                        ),
                    }
                )
            execution = (
                read(directory / "result.json")
                if (directory / "result.json").exists()
                else {}
            )
            resource = call_resources(review["stage"])
            resource_rows.append(
                {
                    "group": group,
                    "project_id": project,
                    "stage_id": review["stage_id"],
                    "execution": execution.get("execution", "receipt_before_final"),
                    **resource,
                    "seconds": review["wall_seconds"],
                    "interrupted_segment_seconds_unknown": review.get(
                        "wall_seconds_excludes_unmeasured_interrupted_segment", False
                    ),
                    "unreceipted_inflight_call_cannot_be_excluded": bool(
                        review.get("process_recovery_archive")
                    ),
                    "response_models": sorted(
                        {
                            r.get("response_model")
                            for r in review["stage"]["model_calls"]
                            if r.get("response_model")
                        }
                    ),
                    "error": review["stage"].get("error"),
                }
            )
            stage_ids.add(review["stage_id"])
            per.append(
                {
                    "group": group,
                    "project_id": project,
                    **{
                        k: after[0][k]
                        for k in (
                            "tp",
                            "fp",
                            "fn",
                            "tn",
                            "precision",
                            "recall",
                            "f1",
                            "f3",
                        )
                    },
                    "status": review["stage"]["status"],
                    "gold_vulnerabilities": after[0]["tp"] + after[0]["fn"],
                    "coverage_status": review["stage"]["result"].get("coverage_status"),
                    "candidate_states": dict(
                        Counter(c["model_assessment"] for c in review["candidates"])
                    ),
                    "review_calls": resource["calls"],
                    "review_input_tokens_known": resource["input_tokens"],
                    "review_output_tokens_known": resource["output_tokens"],
                    "unknown_usage_calls": resource["unknown_usage_calls"],
                    "review_wall_seconds": review["wall_seconds"],
                    "interrupted_segment_seconds_unknown": review.get(
                        "wall_seconds_excludes_unmeasured_interrupted_segment", False
                    ),
                    "window_inspected": coverage.get(
                        "inspected_eligible_windows", coverage.get("inspected_windows")
                    )
                    if group in {"E", "F"}
                    else None,
                    "window_eligible": coverage.get("eligible_windows")
                    if group in {"E", "F"}
                    else None,
                    "adopted_chain_seconds": review["wall_seconds"]
                    + float(
                        discovery_rows[("B" if group in {"E", "F"} else "A", project)][
                            "wall_seconds_adopted"
                        ]
                    ),
                    "adopted_static_extra_seconds": float(
                        discovery_rows[("A", project)]["wall_seconds_adopted"]
                    )
                    if group == "F"
                    else 0,
                    "execution": execution.get("execution"),
                    "receipt": str(path),
                }
            )
        resources = [r for r in resource_rows if r["group"] == group]
        complete = len(cards[group]) == 26
        aggregate = metrics(cards[group]) if complete else {}
        summary.append(
            {
                "group": group,
                "status": (
                    "uniform_v3_review"
                    if group == "D"
                    else "uniform_v3_review_frozen_incremental_scout"
                )
                if complete
                else "in_progress_metrics_pending_26_projects",
                **aggregate,
                "projects_frozen": 26,
                "projects_scored": len(cards[group]),
                "input_transition_states": dict(
                    Counter(
                        r["review_state"]
                        for r in all_transitions
                        if r["group"] == group
                    )
                ),
                "candidate_states": dict(
                    sum(
                        (
                            Counter(r["candidate_states"])
                            for r in per
                            if r["group"] == group
                            and isinstance(r.get("candidate_states"), dict)
                        ),
                        Counter(),
                    )
                ),
                "stage_statuses": dict(
                    Counter(
                        r["status"]
                        for r in per
                        if r["group"] == group and r.get("review_calls") is not None
                    )
                ),
                "gold_vulnerabilities": 676,
                "review_calls_new": sum(
                    r["calls"]
                    for r in resources
                    if r["execution"] == "new_independent_review"
                ),
                "review_calls_reused": sum(
                    r["calls"]
                    for r in resources
                    if r["execution"] == "historical_v3_reuse"
                ),
                "review_input_tokens_known": sum(r["input_tokens"] for r in resources),
                "review_output_tokens_known": sum(
                    r["output_tokens"] for r in resources
                ),
                "unknown_usage_calls": sum(r["unknown_usage_calls"] for r in resources),
                "review_wall_seconds": sum(r["seconds"] for r in resources),
                "unmeasured_interrupted_segments": sum(
                    r["interrupted_segment_seconds_unknown"] for r in resources
                ),
                "window_inspected": sum(
                    r.get("window_inspected") or 0 for r in per if r["group"] == group
                )
                if group in {"E", "F"} and complete
                else None,
                "window_eligible": sum(
                    r.get("window_eligible") or 0 for r in per if r["group"] == group
                )
                if group in {"E", "F"} and complete
                else None,
            }
        )
        upstream = (
            next(r for r in summary if r["group"] == "B") if group in {"E", "F"} else {}
        )
        summary[-1].update(
            upstream_calls_reused=upstream.get("calls_reused", 0),
            upstream_input_tokens_known=upstream.get("input_tokens_known", 0),
            upstream_output_tokens_known=upstream.get("output_tokens_known", 0),
            upstream_unknown_usage_calls=upstream.get("unknown_usage_calls", 0),
        )
    csv_write(output / "ablation-summary.csv", summary, display_metrics=True)
    csv_write(output / "ablation-per-project.csv", per, display_metrics=True)
    if all_transitions:
        csv_write(output / "review-transitions.csv", all_transitions)
        csv_write(output / "review-gold-transitions.csv", gold_transitions)
        csv_write(output / "review-resources.csv", resource_rows)
    save(
        output / "formal-summary.json",
        {
            "summary": summary,
            "finished": all(len(cards[g]) == 26 for g in "DEF"),
            "review_gold_transitions": {
                g: dict(
                    Counter(
                        r["transition"] for r in gold_transitions if r["group"] == g
                    )
                )
                for g in "DEF"
            },
            "adopted_review_stage_ids": sorted(stage_ids),
            "new_review_stage_ids": sorted(
                r["stage_id"]
                for r in resource_rows
                if r["execution"] == "new_independent_review"
            ),
            "historical_stage_resources": historical[
                "all_attempt_resources_unique_stages"
            ],
            "new_execution_resources": {
                key: sum(
                    r[key]
                    for r in resource_rows
                    if r["execution"] == "new_independent_review"
                )
                for key in (
                    "calls",
                    "input_tokens",
                    "output_tokens",
                    "unknown_usage_calls",
                )
            },
        },
    )
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(report(args.base.resolve(), args.output.resolve()))


if __name__ == "__main__":
    main()
