"""Explain score changes without treating unresolved candidates as exclusions."""

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from scripts.benchmarks.realvuln_ablation_io import csv_write, read
from scripts.benchmarks.realvuln_prepare import save


def payload(row, field, default):
    return json.loads(row[field]) if row.get(field) else default


def diagnose(output):
    rows = list(csv.DictReader((output / "review-transitions.csv").open()))
    aggregates, project_rows = {}, []
    for group in "DEF":
        selected = [r for r in rows if r["group"] == group]
        if not selected:
            continue
        states, entities = Counter(), defaultdict(Counter)
        rejection_candidates, rejection_attempts = defaultdict(set), Counter()
        reasons, missing = Counter(), Counter()
        for row in selected:
            state = row["review_state"]
            states[state] += 1
            for entity in payload(row, "before_scored_entities", []):
                entities[entity["classification"]][state] += 1
            for rejected in payload(row, "rejected_verdicts", []):
                key = rejected.get("reason") or rejected.get("code") or "unspecified"
                rejection_attempts[key] += 1
                rejection_candidates[key].add(row["candidate_id"])
            if state != "supported":
                if row.get("reason"):
                    reasons[row["reason"]] += 1
                for premise in payload(row, "missing_premises", []):
                    missing[
                        json.dumps(premise, ensure_ascii=False, sort_keys=True)
                    ] += 1
        record = {
            "input_transition_states": dict(states),
            "before_scored_entity_states": {k: dict(v) for k, v in entities.items()},
            "cwe_changed_candidates": sum(
                r.get("cwe_changed") == "True" for r in selected
            ),
            "location_changed_candidates": sum(
                r.get("location_changed") == "True" for r in selected
            ),
            "identity_deduplicated_inputs": sum(
                r.get("deduplicated_by_identity") == "True" for r in selected
            ),
            "review_new_or_unlinked_candidates": sum(
                r["source"] == "review_new_or_unlinked" for r in selected
            ),
            "rejected_attempts_by_reason": dict(rejection_attempts),
            "rejected_unique_candidates_by_reason": {
                k: len(v) for k, v in rejection_candidates.items()
            },
            "unresolved_reasons": dict(reasons),
            "unresolved_missing_premises": dict(missing),
        }
        tools, statuses, coverage, stops = Counter(), Counter(), Counter(), Counter()
        reused_tools, last_context_tools = Counter(), Counter()
        actual_states = Counter()
        performance = Counter()
        for path in sorted((output / "arms" / group / "system").glob("*/review.json")):
            review = read(path)
            stage = review["stage"]
            actual_states.update(c["model_assessment"] for c in review["candidates"])
            result = stage["result"]
            performance.update(
                {
                    "scheduled_candidates": result.get("schedule", {}).get(
                        "scheduled_candidates", 0
                    ),
                    "scheduled_batches": result.get("schedule", {}).get(
                        "scheduled_batches", 0
                    ),
                    "durable_batches": len(result.get("batches", [])),
                    "recovery_candidate_ids": len(
                        result.get("recovery_attempted_ids", [])
                    ),
                    "model_calls": len(stage["model_calls"]),
                    "model_call_seconds_known": sum(
                        c.get("seconds") or 0 for c in stage["model_calls"]
                    ),
                    "stage_seconds_known": review["wall_seconds"],
                }
            )
            statuses[stage["status"]] += 1
            coverage[str(result.get("coverage_status"))] += 1
            if result.get("stop_reason") or stage.get("error"):
                stops[result.get("stop_reason") or stage["error"]] += 1
            traces = [t for b in result.get("batches", []) for t in b.get("trace", [])]
            tools.update(t["tool"] for t in traces if t.get("tool"))
            reused_tools.update(
                t["tool"] for t in traces if t.get("tool") and t.get("reused")
            )
            last_context_tools.update(
                t["tool"] for t in result.get("trace", []) if t.get("tool")
            )
            performance["incomplete_batches_without_trace"] += sum(
                b.get("status") == "incomplete" and "trace" not in b
                for b in result.get("batches", [])
            )
            project = path.parent.name
            subset = [r for r in selected if r["project_id"] == project]
            project_rows.append(
                {
                    "group": group,
                    "project_id": project,
                    "status": stage["status"],
                    "coverage_status": result.get("coverage_status"),
                    "input_transition_states": dict(
                        Counter(r["review_state"] for r in subset)
                    ),
                    "candidate_states": dict(
                        Counter(c["model_assessment"] for c in review["candidates"])
                    ),
                    "stop_reason": result.get("stop_reason") or stage.get("error"),
                    "tools": dict(Counter(t["tool"] for t in traces if t.get("tool"))),
                    "receipt": str(path),
                }
            )
        record.update(
            candidate_states=dict(actual_states),
            performance={
                **dict(performance),
                "mean_scheduled_batch_size": performance["scheduled_candidates"]
                / performance["scheduled_batches"]
                if performance["scheduled_batches"]
                else None,
                "scope": "adopted review receipts, including F historical reuse; interrupted unmeasured segment excluded",
            },
            stage_statuses=dict(statuses),
            coverage_statuses=dict(coverage),
            stop_reasons=dict(stops),
            actual_tools=dict(tools),
            reused_tool_observations=dict(reused_tools),
            partial_last_context_trace_tools=dict(last_context_tools),
            tool_count_scope="Recorded successful/partial batch observations including reuse; incomplete batches may lack traces; last-context trace is not a complete stage ledger",
        )
        aggregates[group] = record
    save(output / "review-diagnostics.json", aggregates)
    csv_write(output / "review-diagnostics-per-project.csv", project_rows)
    return aggregates


def discovery_projects(output):
    rows = list(csv.DictReader((output / "discovery-overlap.csv").open()))
    result = []
    for project in sorted({r["project_id"] for r in rows}):
        subset = [r for r in rows if r["project_id"] == project]
        # Read exported booleans; retain the independent versus merged allocation distinction.
        keys = ["codeql_independent_hit", "scout_independent_hit", "C_union_hit"]
        intersection = Counter(
            "both"
            if r[keys[0]] == r[keys[1]] == "True"
            else "codeql_only"
            if r[keys[0]] == "True"
            else "scout_only"
            if r[keys[1]] == "True"
            else "neither"
            for r in subset
        )
        result.append(
            {
                "project_id": project,
                "gold": len(subset),
                **{
                    k: intersection[k]
                    for k in ("both", "codeql_only", "scout_only", "neither")
                },
                **{k: sum(r[k] == "True" for r in subset) for k in keys},
            }
        )
    csv_write(output / "discovery-overlap-per-project.csv", result)


def discovery_metadata(per, summary, origins):
    """Attach discovery-only scope, source receipts and adopted time to A/B/C."""
    for row in per:
        origin = Path(origins[row["project_id"]])
        static_path = origin / "static" / row["project_id"] / "result.json"
        scout_path = origin / "system" / row["project_id"] / "scout.json"
        count_static = len(read(static_path)["rounds"][0]["findings"])
        count_scout = len(read(scout_path)["candidates"])
        group = row["group"]
        count = (count_static if group in "AC" else 0) + (
            count_scout if group in "BC" else 0
        )
        row.update(
            raw_candidates=count,
            candidate_states={"not_reviewed": count},
            static_receipt=str(static_path) if group in "AC" else None,
            scout_receipt=str(scout_path) if group in "BC" else None,
        )
    for row in summary:
        selected = [r for r in per if r["group"] == row["group"]]
        total = sum(r["raw_candidates"] for r in selected)
        row.update(
            raw_candidates=total,
            candidate_states={"not_reviewed": total},
            stage_statuses=dict(Counter(r["status"] for r in selected)),
            window_inspected=sum(int(r.get("window_inspected") or 0) for r in selected)
            if row["group"] in "BC"
            else None,
            window_eligible=sum(int(r.get("window_eligible") or 0) for r in selected)
            if row["group"] in "BC"
            else None,
            wall_seconds_adopted=sum(
                float(r["wall_seconds_adopted"]) for r in selected
            ),
        )
