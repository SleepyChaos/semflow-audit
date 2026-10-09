"""Bounded full-project Agent and unified review pilot on two calibration projects."""

import argparse
import json

from app.services.review import ReviewService
from app.services.scouting import ScoutService
from app.workflows.review import build_review_graph
from app.workflows.scouting import build_scout_graph

from scripts.benchmarks.formal_freeze import OUTPUT, save
from scripts.benchmarks.formal_runtime import (
    checkpoint_stage,
    new_stage,
    register_audit,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--projects", nargs="+", default=["rv-flask", "rv-dvna"])
    parser.add_argument("--max-units", type=int, default=8)
    args = parser.parse_args()
    for project in args.projects:
        audit = register_audit(project)
        directory = OUTPUT / "discovery" / project
        scout = checkpoint_stage(
            directory / "D1.json",
            lambda audit=audit: new_stage(
                audit,
                "scout",
                "1",
                {
                    "max_units": args.max_units,
                    "steps_per_unit": 3,
                    "window_lines": 100,
                    "max_context_chars": 30000,
                },
            ),
            ScoutService,
            build_scout_graph,
        )
        review = checkpoint_stage(
            directory / "D3.json",
            lambda audit=audit: new_stage(
                audit,
                "review",
                "4",
                {
                    "include_scout": True,
                    "max_steps": 4,
                    "max_batches": 4,
                    "batch_size": 4,
                },
            ),
            ReviewService,
            build_review_graph,
        )
        baseline = json.loads((OUTPUT / "static" / project / "result.json").read_text())
        static = baseline["rounds"][0]["findings"]
        supported = [
            r for r in review["candidates"] if r["model_assessment"] == "supported"
        ]
        save(
            directory / "pilot-summary.json",
            {
                "project_id": project,
                "scope": "bounded calibration; root gold adjudication pending",
                "D0_static_alerts": len(static),
                "D1_hypotheses": len(scout["candidates"]),
                "D1_coverage": scout["stage"]["result"].get("coverage"),
                "D2_raw_union_alerts": len(static) + len(scout["candidates"]),
                "D2_note": "Raw union only; no root-count claim",
                "D3_supported_candidates": len(supported),
                "D3_unreviewed": review["stage"]["result"].get(
                    "unreviewed_candidate_ids"
                ),
                "D3_root_relations": review["stage"]["result"].get("root_relations"),
                "precision_recall": "not_scored_until_root_adjudication",
                "scout_plus_review_wall_seconds": scout["wall_seconds"]
                + review["wall_seconds"],
                "timing_note": "Sequential candidate-pool pilot, not concurrent end-to-end latency",
            },
        )


if __name__ == "__main__":
    main()
