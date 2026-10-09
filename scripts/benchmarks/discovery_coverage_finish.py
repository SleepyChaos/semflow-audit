"""Reuse completed V5 scouts/static baselines; recover one refused-read gap and review."""

import json
from pathlib import Path

from app.adapters.snapshot import snapshot_digest
from app.services.review import ReviewService
from app.services.scouting import ScoutService
from app.workflows.review import build_review_graph
from app.workflows.scouting import build_scout_graph

from scripts.benchmarks.discovery_coverage_retest import (
    compact,
    implementation_hashes,
    stage,
)
from scripts.benchmarks.formal_freeze import ROOT, save
from scripts.benchmarks.formal_runtime import checkpoint_stage, register_audit

PREVIOUS = ROOT / "artifacts/research/discovery-coverage/20261006-v2"
OUTPUT = ROOT / "artifacts/research/discovery-coverage/20261006-v3"


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    hashes = implementation_hashes()
    rows = json.loads((PREVIOUS / "inputs.json").read_text())["records"]
    config = {
        "implementation_hashes": hashes,
        "reused_run": PREVIOUS.name,
        "source_hashes": {r["id"]: r["snapshot"] for r in rows},
        "review": {"calls": 48, "tokens": 1000000, "seconds": 1200},
        "scout_recovery": {"calls": 4, "tokens": 100000, "seconds": 240},
        "gui": False,
        "target_services": False,
        "whole_scout_rerun": False,
    }
    path = OUTPUT / "config.json"
    if path.exists() and json.loads(path.read_text()) != config:
        raise RuntimeError("Completion configuration changed; new run ID required")
    save(path, config)
    summary = {"run_id": OUTPUT.name, "projects": [], "formal": False}
    for record in rows:
        project = record["id"]
        if snapshot_digest(Path(record["source"])) != record["snapshot"]:
            raise RuntimeError("Reused source changed")
        full = json.loads((PREVIOUS / project / "full-scout.json").read_text())
        audit = register_audit(project, output=PREVIOUS)
        directory = OUTPUT / project
        source_map = json.loads(
            (ROOT / "artifacts/runs" / full["stage_id"] / "scout-map.json").read_text()
        )
        incomplete = [
            r for r in full["stage"]["result"]["units"] if r["status"] != "inspected"
        ]
        recovered = []
        selected = [r["id"] for r in full["candidates"]]
        combined = {
            r["unit_id"]: r
            for r in full["stage"]["result"]["units"]
            if r["status"] == "inspected"
        }
        for failed in incomplete:
            unit = next(r for r in source_map["units"] if r["id"] == failed["unit_id"])
            inputs = {
                "paths": [unit["file"]],
                "max_units": 100,
                "steps_per_unit": 3,
                "window_lines": 100,
                "include_third_party": False,
            }
            result = checkpoint_stage(
                directory / f"recover-{unit['id']}.json",
                lambda audit=audit, inputs=inputs: stage(
                    audit, "scout", inputs, 4, 100000, 240
                ),
                ScoutService,
                build_scout_graph,
            )
            selected.extend(c["id"] for c in result["candidates"])
            combined.update(
                {
                    r["unit_id"]: r
                    for r in result["stage"]["result"]["units"]
                    if r["status"] == "inspected"
                }
            )
            recovered.append(compact(result))
        eligible = {
            u["id"]
            for u in source_map["units"]
            if u["role_hint"] != "third_party_or_generated"
        }
        inputs = {
            "include_scout": True,
            "scout_candidate_ids": selected,
            "discover": False,
            "max_steps": 6,
            "max_batches": 100,
            "batch_size": 4,
            "max_context_chars": 40000,
        }
        review = checkpoint_stage(
            directory / "full-review.json",
            lambda audit=audit, inputs=inputs: stage(
                audit, "review", inputs, 48, 1000000, 1200
            ),
            ReviewService,
            build_review_graph,
        )
        summary["projects"].append(
            {
                "project": project,
                "snapshot": record["snapshot"],
                "reused_full_scout": compact(full),
                "recovered": recovered,
                "combined_business_windows": len(eligible & set(combined)),
                "eligible_windows": len(eligible),
                "remaining_business_windows": sorted(eligible - set(combined)),
                "task_status_counts": {
                    status: sum(
                        t["status"] == status
                        for r in combined.values()
                        for t in r.get("task_checks", [])
                    )
                    for status in ("investigated", "unknown", "not_applicable")
                },
                "review": compact(review),
            }
        )
        save(OUTPUT / "summary.json", summary)
        if implementation_hashes() != hashes:
            raise RuntimeError("Completion implementation changed during run")
    save(
        OUTPUT / "integrity.json",
        {
            "input_and_implementation_unchanged": True,
            "ordinary_tests": 72,
            "gui": False,
            "target_services": False,
            "prior_paid_scouts_preserved_and_reused": True,
        },
    )
    print(
        json.dumps(
            {
                "run_id": OUTPUT.name,
                "projects": [r["project"] for r in summary["projects"]],
            }
        )
    )


if __name__ == "__main__":
    main()
