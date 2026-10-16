"""Resume an interrupted immutable review pool without replaying complete batches."""

import argparse
import shutil
from pathlib import Path

from app.adapters.snapshot import snapshot_digest
from app.persistence.stage_repository import StageRepository
from app.services.review import ReviewService
from app.workflows.review import build_review_graph
from scripts.benchmarks.formal_runtime import run_stage
from scripts.benchmarks.realvuln_ablation_io import read
from scripts.benchmarks.realvuln_ablation_run import interrupted
from scripts.benchmarks.realvuln_prepare import save
from scripts.benchmarks.realvuln_run import verify_implementation


def resume(output, group, project):
    verify_implementation(output)
    directory = output / "arms" / group / "system" / project
    original = read(directory / "review.json")
    if not interrupted(original):
        raise RuntimeError(
            "Only a recorded provider interruption permits this recovery"
        )
    stage_id = original["stage_id"]
    inputs = read(directory / "input.json")
    source = Path(inputs["origin"]) / "sources" / project
    if snapshot_digest(source) != inputs["snapshot"]:
        raise RuntimeError("Cannot resume a changed input")
    archive = output / "attempts/provider-interruption-1" / group / project
    archive.mkdir(parents=True, exist_ok=False)
    for name in ("review.json", "result.json", "input.json"):
        shutil.copyfile(directory / name, archive / name)
    repository = StageRepository()
    before = repository.get(stage_id)
    if before.model_calls != original["stage"]["model_calls"]:
        raise RuntimeError("Live stage diverges from saved interruption receipt")
    save(
        archive / "resume-event.json",
        {
            "stage_id": stage_id,
            "previous_status": before.status,
            "reason": "APIConnectionError; low-cost inference recovery probe succeeded",
            "same_inputs": True,
            "same_pool_and_candidate_ids": True,
            "existing_batch_ids": [
                b["batch_id"] for b in before.result.get("batches", [])
            ],
            "original_calls": len(before.model_calls),
            "strategy": "same production graph skips durable completed/failed base batches; normal one-attempt unresolved recovery handles interrupted candidate",
        },
    )
    repository.update(stage_id, status="queued", error=None)
    result = run_stage(stage_id, ReviewService, build_review_graph)
    if result["stage"]["model_calls"][: len(before.model_calls)] != before.model_calls:
        raise RuntimeError("Recovery modified original call history")
    result["execution_segments"] = [
        {
            "kind": "before_provider_interruption",
            "seconds": original["wall_seconds"],
            "calls": len(before.model_calls),
        },
        {
            "kind": "same_pool_resume",
            "seconds": result["wall_seconds"],
            "calls": len(result["stage"]["model_calls"]) - len(before.model_calls),
        },
    ]
    result["wall_seconds"] += original["wall_seconds"]
    result["provider_recovery_archive"] = str(archive)
    save(directory / "review.json", result)
    save(
        directory / "result.json",
        {
            "group": group,
            "project_id": project,
            "status": result["stage"]["status"],
            "stage_id": stage_id,
            "execution": "new_independent_review",
            "usage": result["stage"]["usage"],
            "provider_interrupted": interrupted(result),
            "same_pool_resumed": True,
            "original_attempt_retained": str(archive),
        },
    )
    verify_implementation(output)
    print(
        project,
        result["stage"]["status"],
        "total calls",
        len(result["stage"]["model_calls"]),
        "still interrupted",
        interrupted(result),
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--group", choices=["D", "E", "F"], required=True)
    parser.add_argument("--project", required=True)
    args = parser.parse_args()
    resume(args.output.resolve(), args.group, args.project)


if __name__ == "__main__":
    main()
