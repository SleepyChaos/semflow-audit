"""New execution resumes incomplete windows; old stage and calls stay immutable."""

import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import UUID

from app.adapters.ai.policy import policy_snapshot
from app.adapters.codeql.scanner import CodeQLScanner
from app.contracts.stages import ReviewRequest
from app.core.audit_config import audit_settings
from app.core.db import engine
from app.persistence.audit_models import AuditRun
from app.persistence.stage_models import Candidate, StageRun
from app.services.review import ReviewService
from app.services.scout_continuation import continuation_inputs
from app.services.scouting import ScoutService
from app.workflows.review import build_review_graph
from app.workflows.scouting import build_scout_graph
from scripts.benchmarks.formal_runtime import checkpoint_stage
from scripts.benchmarks.realvuln_prepare import save
from scripts.benchmarks.realvuln_run import read, stage, verify_implementation
from scripts.benchmarks.realvuln_static_reuse import reuse_static
from sqlmodel import Session, select


def inherited_candidates(record):
    lineage = record["stage"]["result"].get("source_stage_ids", [])
    if not lineage:
        return record
    with Session(engine) as db:
        ids = [UUID(i) for i in lineage]
        stages = db.exec(
            select(StageRun).where(
                StageRun.id.in_(ids),
                StageRun.audit_id == UUID(record["stage"]["audit_id"]),
                StageRun.kind == "scout",
            )
        ).all()
        if {r.id for r in stages} != set(ids):
            raise RuntimeError("Scout candidate lineage crosses audit or stage kind")
        rows = db.exec(
            select(Candidate).where(Candidate.stage_id.in_([UUID(i) for i in lineage]))
        ).all()
        unique = {r.identity_key: r.model_dump(mode="json") for r in rows}
    unique.update({r["identity_key"]: r for r in record["candidates"]})
    return {
        **record,
        "candidates": list(unique.values()),
        "candidate_lineage_stage_ids": lineage,
    }


def resume_project(project, previous, output, config):
    directory = output / "system" / project
    if (directory / "result.json").exists():
        return read(directory / "result.json")
    verify_implementation(output)
    row = read(output / "acquisition" / f"{project}.json")
    static = reuse_static(row, output, config)
    original = read(previous / "system" / project / "scout.json")
    audit_id = original["stage"]["audit_id"]
    save(
        output / "audits" / f"{project}.json",
        read(previous / "audits" / f"{project}.json"),
    )
    coverage = original["stage"]["result"]["coverage"]
    eligible = coverage.get("eligible_windows", coverage["planned_windows"])
    inspected = coverage.get(
        "inspected_eligible_windows", coverage["inspected_windows"]
    )
    if inspected < eligible:

        def create_scout():
            with Session(engine) as db:
                old = db.get(StageRun, UUID(original["stage_id"]))
                audit = db.get(AuditRun, UUID(audit_id))
                inputs, initial = continuation_inputs(old, audit, db)
            return stage(
                audit_id,
                "scout",
                "7",
                inputs,
                config["model_policies"]["scout"],
                initial,
            )

        scout = checkpoint_stage(
            directory / "scout.json", create_scout, ScoutService, build_scout_graph
        )
        scout = inherited_candidates(scout)
        save(directory / "scout.json", scout)
        scout_usage = scout["stage"]["usage"]
    else:
        scout = {
            **original,
            "inherited_completed_scout": True,
            "inherited_from": str(previous),
        }
        scout_usage = {"calls": 0, "input_tokens": 0, "output_tokens": 0}
        save(directory / "scout.json", scout)
    review = checkpoint_stage(
        directory / "review.json",
        lambda: stage(
            audit_id,
            "review",
            "12",
            ReviewRequest().model_dump(mode="json"),
            config["model_policies"]["review"],
        ),
        ReviewService,
        build_review_graph,
    )
    coverage = scout["stage"]["result"]["coverage"]
    result = {
        "project_id": project,
        "audit_id": audit_id,
        "static_status": static["status"],
        "static_seconds": 0,
        "scout_stage_id": scout["stage_id"],
        "review_stage_id": review["stage_id"],
        "scout_status": scout["stage"]["status"],
        "review_status": review["stage"]["status"],
        "scout_coverage": coverage,
        "review_coverage": review["stage"]["result"].get("coverage_status"),
        "scout_candidates": len(scout["candidates"]),
        "supported_candidates": sum(
            c["model_assessment"] == "supported" for c in review["candidates"]
        ),
        "excluded_candidates": sum(
            c["model_assessment"] == "excluded" for c in review["candidates"]
        ),
        "unresolved_candidates": sum(
            c["model_assessment"] not in {"supported", "excluded"}
            for c in review["candidates"]
        ),
        "scout_usage": scout_usage,
        "review_usage": review["stage"]["usage"],
        "scout_seconds": 0
        if scout.get("inherited_completed_scout")
        else scout["wall_seconds"],
        "review_seconds": review["wall_seconds"],
        "recovery_from": str(previous),
        "baseline_reused": True,
        "integrity_verified": True,
    }
    result["sequential_chain_seconds"] = (
        result["scout_seconds"] + result["review_seconds"]
    )
    result["status"] = (
        "completed"
        if coverage.get("business_coverage_status") == "completed"
        and result["review_coverage"] == "completed"
        else "partial"
    )
    verify_implementation(output)
    save(directory / "result.json", result)
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "project_id",
                    "status",
                    "supported_candidates",
                    "unresolved_candidates",
                )
            }
        ),
        flush=True,
    )
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--v2", type=Path, required=True)
    parser.add_argument("--retest", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    v2, retest = args.v2.resolve(), args.retest.resolve()
    old_config = read(v2 / "config.json")
    config = {
        **old_config,
        "codeql_cli": CodeQLScanner().version(),
        "model_policies": {kind: policy_snapshot(kind) for kind in ("scout", "review")},
        "reuse_static_from": str(v2),
        "recovery_run": True,
    }
    config["runtime_paths"] = {
        "packs": str(audit_settings.CODEQL_PACK_PATH),
        "artifacts": str(audit_settings.ARTIFACT_ROOT),
    }
    if (output / "config.json").exists() and read(output / "config.json") != config:
        raise RuntimeError("Cannot resume with changed recovery configuration")
    save(output / "config.json", config)
    targets = [
        (p, retest)
        for p in (
            "realvuln-pygoat",
            "realvuln-python-app",
            "realvuln-python-insecure-app",
        )
    ]
    targets += [(p, v2) for p in ("realvuln-vulnpy", "realvuln-vulpy")]
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(resume_project, p, previous, output, config)
            for p, previous in targets
        ]
        rows = [future.result() for future in futures]
    save(output / "run-summary.json", {"projects": rows, "total_targets": len(targets)})


if __name__ == "__main__":
    main()
