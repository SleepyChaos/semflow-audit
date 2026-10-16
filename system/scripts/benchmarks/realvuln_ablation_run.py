"""Actual isolated D/E review runs and v3-consistent F review completion."""

import argparse
from pathlib import Path

from app.contracts.stages import ReviewRequest
from app.services.review import ReviewService
from app.workflows.review import build_review_graph
from scripts.benchmarks.formal_runtime import checkpoint_stage
from scripts.benchmarks.realvuln_ablation import catalog
from scripts.benchmarks.realvuln_ablation_inputs import register
from scripts.benchmarks.realvuln_ablation_io import read
from scripts.benchmarks.realvuln_prepare import save
from scripts.benchmarks.realvuln_run import stage, verify_implementation


def interrupted(record):
    calls = record["stage"].get("model_calls", [])
    return bool(
        calls
        and calls[-1].get("error_code") in {"rate_limited", "provider_error", "timeout"}
    )


def run(base, output):
    verify_implementation(output)
    config = read(output / "config.json")
    origins = read(base / "20261013-progress-v3-retest/incremental-report-data.json")[
        "provenance"
    ]
    history = catalog(base)
    frozen_v3 = read(base / "20261013-progress-v3-retest/implementation-hashes.json")
    for group in ("D", "E", "F"):
        for project, location in origins.items():
            origin = Path(location)
            directory = output / "arms" / group / "system" / project
            final = directory / "result.json"
            if final.exists():
                continue
            original = read(origin / "system" / project / "review.json")
            original_hashes = read(origin / "implementation-hashes.json")
            if group == "F" and original_hashes == frozen_v3:
                save(directory / "review.json", original)
                save(
                    final,
                    {
                        "group": group,
                        "project_id": project,
                        "status": original["stage"]["status"],
                        "stage_id": original["stage_id"],
                        "execution": "historical_v3_reuse",
                        "new_calls": 0,
                        "original_receipt": str(
                            origin / "system" / project / "review.json"
                        ),
                    },
                )
                continue
            inputs = register(project, group, origin, output, history)
            request = ReviewRequest(include_scout=group != "D")
            review = checkpoint_stage(
                directory / "review.json",
                lambda inputs=inputs, request=request: stage(
                    inputs["audit_id"],
                    "review",
                    "12",
                    request.model_dump(mode="json"),
                    config["review_policy"],
                ),
                ReviewService,
                build_review_graph,
            )
            save(
                final,
                {
                    "group": group,
                    "project_id": project,
                    "status": review["stage"]["status"],
                    "stage_id": review["stage_id"],
                    "execution": "new_independent_review",
                    "usage": review["stage"]["usage"],
                    "provider_interrupted": interrupted(review),
                },
            )
            verify_implementation(output)
            if interrupted(review):
                save(
                    output / "pipeline-status.json",
                    {
                        "status": "provider_interrupted",
                        "group": group,
                        "project_id": project,
                    },
                )
                return
    save(output / "pipeline-status.json", {"status": "finished", "review_projects": 78})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.base.resolve(), args.output.resolve())


if __name__ == "__main__":
    main()
