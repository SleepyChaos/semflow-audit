"""Recover a process interruption before its first persisted model call."""

import argparse
from pathlib import Path

from app.adapters.snapshot import snapshot_digest
from app.persistence.stage_repository import StageRepository
from app.services.review import ReviewService
from app.workflows.review import build_review_graph
from scripts.benchmarks.formal_runtime import run_stage, stage_record
from scripts.benchmarks.realvuln_ablation_io import read
from scripts.benchmarks.realvuln_ablation_run import interrupted
from scripts.benchmarks.realvuln_prepare import save
from scripts.benchmarks.realvuln_run import verify_implementation


def recover(output, group, project):
    verify_implementation(output)
    directory = output / "arms" / group / "system" / project
    if (directory / "review.json").exists():
        raise RuntimeError("Existing receipt requires ordinary provider recovery")
    identifier = read(directory / "review.started.json")["stage_id"]
    inputs = read(directory / "input.json")
    if (
        snapshot_digest(Path(inputs["origin"]) / "sources" / project)
        != inputs["snapshot"]
    ):
        raise RuntimeError("Source changed")
    before = stage_record(identifier, None)
    stage = before["stage"]
    if (
        stage["status"] != "running"
        or stage["model_calls"]
        or stage["result"].get("batches")
    ):
        raise RuntimeError(
            "Recovery only supports a prepared pool without persisted calls"
        )
    archive = output / "attempts/process-interruption-1" / group / project
    archive.mkdir(parents=True, exist_ok=False)
    save(archive / "before.json", before)
    save(
        archive / "recovery-event.json",
        {
            "stage_id": identifier,
            "reason": "Process absent after account-limit interruption",
            "same_pool_and_stage": True,
            "original_wall_seconds": None,
            "unreceipted_inflight_call_cannot_be_excluded": True,
            "cost_limit": "Only persisted provider receipts can be accounted for",
        },
    )
    StageRepository().update(identifier, status="queued", error=None)
    result = run_stage(identifier, ReviewService, build_review_graph)
    if result["stage"]["result"].get("pool") != stage["result"].get("pool"):
        raise RuntimeError("Recovery changed candidate pool")
    result["process_recovery_archive"] = str(archive)
    result["wall_seconds_excludes_unmeasured_interrupted_segment"] = True
    save(directory / "review.json", result)
    save(
        directory / "result.json",
        {
            "group": group,
            "project_id": project,
            "status": result["stage"]["status"],
            "stage_id": identifier,
            "execution": "new_independent_review",
            "usage": result["stage"]["usage"],
            "provider_interrupted": interrupted(result),
            "same_pool_resumed": True,
            "original_attempt_retained": str(archive),
        },
    )
    print(
        project,
        result["stage"]["status"],
        "calls",
        len(result["stage"]["model_calls"]),
        flush=True,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--group", choices=["D", "E", "F"], required=True)
    parser.add_argument("--project", required=True)
    args = parser.parse_args()
    recover(args.output.resolve(), args.group, args.project)


if __name__ == "__main__":
    main()
