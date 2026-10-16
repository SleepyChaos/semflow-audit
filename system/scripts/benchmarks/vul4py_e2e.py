"""Full-source CodeQL → Scout7 → Review12 → Repair2, without gold hints."""

import argparse
import json
import shutil
from pathlib import Path
from uuid import UUID

from app.adapters.snapshot import snapshot_digest
from app.contracts.scouting import ScoutRequest
from app.contracts.stages import RepairRequest, ReviewRequest
from app.core.db import engine
from app.domain.audit import AuditError
from app.persistence.stage_models import RepairRecord
from app.services.repair import RepairService
from app.services.review import ReviewService
from app.services.scouting import ScoutService
from app.workflows.repair import build_repair_graph
from app.workflows.review import build_review_graph
from app.workflows.scouting import build_scout_graph
from scripts.benchmarks.formal_baseline import run_one
from scripts.benchmarks.formal_runtime import checkpoint_stage, register_audit
from scripts.benchmarks.full_test_progress import collect
from scripts.benchmarks.realvuln_run import stage, verify_implementation
from scripts.benchmarks.vul4py_prepare import save
from scripts.benchmarks.vul4py_repair import evaluate_candidate
from sqlmodel import Session, select


def read(path):
    return json.loads(path.read_text())


def provider_interrupted(receipt):
    calls = receipt["stage"].get("model_calls", [])
    return bool(calls) and calls[-1].get("error_code") in {
        "rate_limited",
        "provider_error",
        "timeout",
    }


def provider_streak(previous, result):
    if result.get("provider_interrupted"):
        return previous + 1
    return previous if result["status"] == "input_failed" else 0


def evaluate(identity, project, candidate_id, record, root):
    calibration = read(root / "calibration" / identity / "result.json")
    if not calibration["accepted"]:
        return {
            "status": "not_evaluated",
            "reason": "oracle_not_calibrated",
            "joint_pass": False,
        }
    # Each independent candidate has its own evaluator. Nothing from here enters
    # the production audit source, review inputs, repair evidence or feedback.
    output = root / "e2e" / "candidate-evaluations" / candidate_id
    case = output / "evaluator" / project
    case.mkdir(parents=True, exist_ok=True)
    (output / "runs" / project).mkdir(parents=True, exist_ok=True)
    for name in ("upstream", "evaluator-tools"):
        alias = output / name
        if not alias.exists():
            alias.symlink_to(root / name, target_is_directory=True)
    source = root / "workspaces" / identity
    if not (case / "meta.json").exists():
        shutil.copytree(source / "fixed", case / "fixed", symlinks=True)
        shutil.copyfile(source / "meta.json", case / "meta.json")
    image = read(root / "oracle-config.json")["image_id"]
    return evaluate_candidate(project, record, output, image)


def repair_candidate(candidate, audit, project, identity, config, root):
    output = root / "e2e"
    directory = output / "system" / project / "repairs" / candidate["id"]
    final = directory / "result.json"
    if final.exists():
        return read(final)
    from app.adapters.repair.readiness import target_readiness

    readiness = target_readiness(
        output / "sources" / project, [candidate.get("location", {}).get("file", "")]
    )
    if readiness["status"] != "eligible":
        result = {
            "candidate_id": candidate["id"],
            "status": readiness["status"],
            "reason": readiness["reason"],
            "joint_pass": False,
            "human_correct": None,
            "model_dispatched": False,
        }
        save(final, result)
        return result
    inputs = RepairRequest(candidate_ids=[candidate["id"]], rescan=True)
    generation = checkpoint_stage(
        directory / "generation.json",
        lambda: stage(
            audit,
            "repair",
            config["versions"].get("repair", "2"),
            inputs.model_dump(mode="json"),
            config["repair_policy"],
        ),
        RepairService,
        build_repair_graph,
    )
    result = {
        "candidate_id": candidate["id"],
        "status": "repair_failed",
        "joint_pass": False,
        "stage_id": generation["stage_id"],
        "stage_status": generation["stage"]["status"],
        "usage": generation["stage"]["usage"],
        "reason": generation["stage"].get("error"),
        "provider_interrupted": provider_interrupted(generation),
        "human_correct": None,
    }
    with Session(engine) as db:
        record = db.exec(
            select(RepairRecord).where(
                RepairRecord.stage_id == UUID(generation["stage_id"])
            )
        ).first()
    if record:
        result.update(evaluate(identity, project, candidate["id"], record, root))
    save(final, result)
    return result


def run_project(row, identity, config, root):
    output = root / "e2e"
    directory = output / "system" / row["id"]
    final = directory / "result.json"
    if final.exists():
        return read(final)
    result = {
        "project_id": row["id"],
        "status": "input_failed",
        "joint_pass": False,
        "human_correct": None,
    }
    if row["status"] != "prepared":
        result["error"] = row.get("error")
        save(final, result)
        return result
    verify_implementation(root)
    if snapshot_digest(Path(row["source"])) != row["snapshot"]:
        raise RuntimeError("Frozen end-to-end source changed")
    static = run_one(row, config, 1, output)
    result.update(static_status=static["status"], static_seconds=static["wall_seconds"])
    if static["status"] != "succeeded":
        result.update(status="blocked_static_failure", error=static.get("error"))
        save(final, result)
        return result
    audit = register_audit(row["id"], output)
    result["audit_id"] = audit
    scout = checkpoint_stage(
        directory / "scout.json",
        lambda: stage(
            audit,
            "scout",
            "7",
            ScoutRequest(**config.get("scout_request", {})).model_dump(mode="json"),
            config["model_policies"]["scout"],
        ),
        ScoutService,
        build_scout_graph,
    )
    result.update(
        scout_status=scout["stage"]["status"],
        scout_coverage=scout["stage"]["result"].get("coverage", {}),
        scout_usage=scout["stage"]["usage"],
    )
    if provider_interrupted(scout):
        result.update(status="provider_interrupted", provider_interrupted=True)
        save(final, result)
        return result
    review = checkpoint_stage(
        directory / "review.json",
        lambda: stage(
            audit,
            "review",
            "12",
            ReviewRequest().model_dump(mode="json"),
            config["model_policies"]["review"],
        ),
        ReviewService,
        build_review_graph,
    )
    result.update(
        review_status=review["stage"]["status"],
        review_coverage=review["stage"]["result"].get("coverage_status"),
        review_usage=review["stage"]["usage"],
    )
    if provider_interrupted(review):
        result.update(status="provider_interrupted", provider_interrupted=True)
        save(final, result)
        return result
    confirmed = sorted(
        (
            c
            for c in review["candidates"]
            if c["status"] == "confirmed" and c["model_assessment"] == "supported"
        ),
        key=lambda c: c["id"],
    )
    save(
        directory / "repair-selection.json",
        {"candidates": confirmed, "selection": config["repair_selection"]},
    )
    repairs = []
    for candidate in confirmed:
        repairs.append(
            repair_candidate(candidate, audit, row["id"], identity, config, root)
        )
        if repairs[-1].get("provider_interrupted"):
            break
    result.update(
        confirmed_candidates=len(confirmed),
        unresolved_candidates=sum(
            c["model_assessment"] not in {"supported", "excluded"}
            for c in review["candidates"]
        ),
        repairs=repairs,
        joint_pass=any(r["joint_pass"] for r in repairs),
        repair_attempted=len(repairs),
        status="completed"
        if scout["stage"]["status"] == review["stage"]["status"] == "completed"
        and result["scout_coverage"].get("status")
        == result["review_coverage"]
        == "completed"
        else "partial",
        provider_interrupted=any(r.get("provider_interrupted") for r in repairs),
    )
    if not confirmed:
        result["repair_status"] = "not_started_no_ai_confirmed_candidate"
    if result["provider_interrupted"]:
        result["status"] = "provider_interrupted"
    verify_implementation(root)
    if snapshot_digest(Path(row["source"])) != row["snapshot"]:
        raise RuntimeError("Original source mutated during end-to-end chain")
    result["integrity_verified"] = True
    save(final, result)
    print(
        row["id"],
        result["status"],
        "confirmed",
        len(confirmed),
        "joint_pass",
        result["joint_pass"],
        flush=True,
    )
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--isolate-project-failures", action="store_true")
    args = parser.parse_args()
    root = args.output.resolve()
    # Enforce the user's requested ordering, even when this is invoked directly.
    repair_summary = read(root / "repair-summary.json")
    if repair_summary.get("attempted") != 100 or not repair_summary.get(
        "all_tasks_have_status"
    ):
        raise RuntimeError(
            "Complete all 100 repair-only task outcomes before end-to-end execution"
        )
    progress = collect(root)
    if not progress["known_location_repair"]["ready_for_e2e"]:
        raise RuntimeError(
            "Resolve missing/invalid receipts and infrastructure interruptions before end-to-end execution"
        )
    output = root / "e2e"
    config = read(output / "config.json")
    mapping = {
        r["project_id"]: r["vuln_id"]
        for r in read(output / "evaluator-only-mapping.json")["records"]
    }
    rows = read(output / "inputs.json")["records"]
    consecutive_provider_failures = 0
    for row in rows:
        try:
            result = run_project(row, mapping[row["id"]], config, root)
        except (OSError, RuntimeError, ValueError, AuditError) as error:
            result = {
                "project_id": row["id"],
                "status": "runner_failed",
                "error": str(error),
                "joint_pass": False,
            }
            save(output / "system" / row["id"] / "result.json", result)
        completed = [
            read(output / "system" / r["id"] / "result.json")
            for r in rows
            if (output / "system" / r["id"] / "result.json").exists()
        ]
        save(
            output / "summary.json",
            {
                "total_frozen": 100,
                "terminal_tasks": len(completed),
                "joint_pass": sum(r["joint_pass"] for r in completed),
                "cases": completed,
                "human_correct": None,
            },
        )
        consecutive_provider_failures = provider_streak(
            consecutive_provider_failures, result
        )
        if result.get("provider_interrupted") and (
            not args.isolate_project_failures or consecutive_provider_failures >= 3
        ):
            save(
                output / "pipeline-status.json",
                {
                    "status": "provider_interrupted",
                    "project_id": row["id"],
                    "consecutive_provider_failures": consecutive_provider_failures,
                },
            )
            return
    save(output / "pipeline-status.json", {"status": "finished", "terminal_tasks": 100})


if __name__ == "__main__":
    main()
