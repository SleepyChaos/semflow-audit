"""A disjoint secondary F queue; preassigned markers prevent duplicate dispatch."""

import argparse
from pathlib import Path

from app.contracts.stages import ReviewRequest
from app.services.review import ReviewService
from app.workflows.review import build_review_graph
from scripts.benchmarks.formal_runtime import run_stage
from scripts.benchmarks.realvuln_ablation import catalog
from scripts.benchmarks.realvuln_ablation_inputs import register
from scripts.benchmarks.realvuln_ablation_io import read
from scripts.benchmarks.realvuln_ablation_run import interrupted
from scripts.benchmarks.realvuln_prepare import save
from scripts.benchmarks.realvuln_run import stage, verify_implementation

PROJECTS = (
    "realvuln-threatbyte",
    "realvuln-vampi",
    "realvuln-vfapi",
    "realvuln-vulnerable-api",
    "realvuln-vulnerable-flask-app",
    "realvuln-vulnerable-python-apps",
    "realvuln-vulnerable-tornado-app",
)


def run(base, output):
    verify_implementation(output)
    origins = read(base / "20261013-progress-v3-retest/incremental-report-data.json")[
        "provenance"
    ]
    config, history = read(output / "config.json"), catalog(base)
    assignment = output / "secondary-queue.json"
    if assignment.exists():
        raise RuntimeError(
            "Existing secondary queue requires explicit checkpoint recovery"
        )
    # The primary is still several projects before this disjoint seven-project
    # suffix. Reserve every ID before invoking a model. Its existing marker guard
    # stops the primary if it catches up to an unfinished reserved project.
    records = []
    for project in PROJECTS:
        directory = output / "arms/F/system" / project
        marker = directory / "review.started.json"
        if marker.exists() or (directory / "review.json").exists():
            raise RuntimeError(f"Project already dispatched: {project}")
        inputs = register(project, "F", Path(origins[project]), output, history)
        identifier = stage(
            inputs["audit_id"],
            "review",
            "12",
            ReviewRequest(include_scout=True).model_dump(mode="json"),
            config["review_policy"],
        )
        save(marker, {"stage_id": identifier, "dispatch_owner": "secondary_queue"})
        records.append(
            {
                "project_id": project,
                "stage_id": identifier,
                "audit_id": inputs["audit_id"],
            }
        )
    if len({r["stage_id"] for r in records}) != len(PROJECTS):
        raise RuntimeError("Stage identity collision")
    save(
        assignment,
        {
            "status": "reserved",
            "maximum_total_project_concurrency": 2,
            "primary_marker_guard_handoff_expected": True,
            "projects": records,
        },
    )
    for record in records:
        if read(output / "pipeline-status.json")["status"] == "provider_interrupted":
            raise RuntimeError("Provider interruption halted dispatch")
        project, identifier = record["project_id"], record["stage_id"]
        directory = output / "arms/F/system" / project
        review = run_stage(identifier, ReviewService, build_review_graph)
        if review["stage"]["status"] == "running":
            raise RuntimeError("Another dispatcher claimed the reserved stage")
        save(directory / "review.json", review)
        save(
            directory / "result.json",
            {
                "group": "F",
                "project_id": project,
                "status": review["stage"]["status"],
                "stage_id": identifier,
                "execution": "new_independent_review",
                "usage": review["stage"]["usage"],
                "provider_interrupted": interrupted(review),
                "dispatch_owner": "secondary_queue",
            },
        )
        verify_implementation(output)
        print(
            project,
            review["stage"]["status"],
            len(review["stage"]["model_calls"]),
            flush=True,
        )
        if interrupted(review):
            save(
                output / "pipeline-status.json",
                {"status": "provider_interrupted", "group": "F", "project_id": project},
            )
            return
    save(
        assignment,
        {
            "status": "completed",
            "maximum_total_project_concurrency": 2,
            "primary_marker_guard_handoff_expected": True,
            "projects": records,
        },
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.base.resolve(), args.output.resolve())


if __name__ == "__main__":
    main()
