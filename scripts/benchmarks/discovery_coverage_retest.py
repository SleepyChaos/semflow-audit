"""V4 equal-cap scout plus separately budgeted complete business investigation/review."""

import hashlib
import json
import shutil
from pathlib import Path
from uuid import UUID

from app.adapters.ai.policy import policy_snapshot
from app.adapters.snapshot import snapshot_digest
from app.core.db import engine
from app.persistence.stage_models import StageRun
from app.services.review import ReviewService
from app.services.scouting import ScoutService
from app.workflows.review import build_review_graph
from app.workflows.scouting import build_scout_graph
from sqlmodel import Session

from scripts.benchmarks.discovery_coverage_inputs import prepare_inputs
from scripts.benchmarks.formal_baseline import run_one
from scripts.benchmarks.formal_freeze import OUTPUT as PREVIOUS
from scripts.benchmarks.formal_freeze import ROOT, save
from scripts.benchmarks.formal_runtime import checkpoint_stage, register_audit

OUTPUT = ROOT / "artifacts/research/discovery-coverage/20261006-v2"


def implementation_hashes():
    return {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for folder in ("backend/app", "scripts/benchmarks")
        for p in (ROOT / folder).rglob("*")
        if p.is_file() and p.suffix in {".py", ".txt"}
    }


def stage(audit, kind, inputs, calls, tokens, seconds, review_version="6"):
    policy = policy_snapshot()
    policy.update(max_calls=calls, max_tokens=tokens, max_seconds=seconds)
    with Session(engine) as db:
        row = StageRun(
            audit_id=UUID(audit),
            kind=kind,
            prompt_version="5" if kind == "scout" else review_version,
            inputs=inputs,
            model_config_snapshot=policy,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return str(row.id)


def compact(row):
    result = row["stage"]["result"]
    return {
        "stage_id": row["stage_id"],
        "status": row["stage"]["status"],
        "usage": row["stage"]["usage"],
        "wall_seconds": row["wall_seconds"],
        "candidate_count": len(row["candidates"]),
        "coverage": result.get("coverage", result.get("coverage_status")),
        "unreviewed": len(result.get("unreviewed_candidate_ids", [])),
        "verdict_counts": {
            v: sum(r["recommendation"] == v for r in result.get("recommendations", []))
            for v in ("supported", "insufficient", "excluded", "pending")
        },
    }


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    config_path = OUTPUT / "config.json"
    hashes = implementation_hashes()
    old_config = json.loads((PREVIOUS / "config.json").read_text())
    config = {
        "implementation_hashes": hashes,
        "codeql_cli": old_config["codeql_cli"],
        "packs": old_config["packs"],
        "model": policy_snapshot()["model"],
        "equal_cap": {"calls": 12, "tokens": 100000, "seconds": 240, "max_units": 8},
        "full_scout": {
            "calls": 128,
            "tokens": 1000000,
            "seconds": 1200,
            "max_units": 100,
        },
        "full_review": {"calls": 48, "tokens": 1000000, "seconds": 1200},
        "gui": False,
        "target_services": False,
        "labels_into_model": False,
    }
    if config_path.exists() and json.loads(config_path.read_text()) != config:
        raise RuntimeError("Run implementation/config changed; create a new run ID")
    save(config_path, config)
    rows = prepare_inputs(OUTPUT)
    summary = {"run_id": OUTPUT.name, "formal": False, "projects": []}
    for record in rows:
        project = record["id"]
        old = json.loads((PREVIOUS / "static" / project / "result.json").read_text())
        if old["snapshot"] == record["snapshot"]:
            baseline_dir = OUTPUT / "static" / project
            baseline_dir.mkdir(parents=True, exist_ok=True)
            if not (baseline_dir / "result.json").exists():
                (baseline_dir / "database").symlink_to(
                    (PREVIOUS / "static" / project / "database").resolve(),
                    target_is_directory=True,
                )
                shutil.copyfile(
                    PREVIOUS / "static" / project / "round-1.sarif",
                    baseline_dir / "round-1.sarif",
                )
                save(
                    baseline_dir / "result.json",
                    {**old, "reused_unchanged_snapshot": True},
                )
        else:
            run_one(record, config, 1, output=OUTPUT)
        audit = register_audit(project, output=OUTPUT)
        directory = OUTPUT / project
        common = {
            "steps_per_unit": 3,
            "window_lines": 100,
            "max_context_chars": 30000,
            "include_third_party": False,
        }
        equal = checkpoint_stage(
            directory / "equal-scout.json",
            lambda audit=audit, common=common: stage(
                audit, "scout", {**common, "max_units": 8}, 12, 100000, 240
            ),
            ScoutService,
            build_scout_graph,
        )
        full = checkpoint_stage(
            directory / "full-scout.json",
            lambda audit=audit, common=common: stage(
                audit, "scout", {**common, "max_units": 100}, 128, 1000000, 1200
            ),
            ScoutService,
            build_scout_graph,
        )
        if not full["candidates"]:
            raise RuntimeError(
                "Empty scout: explicit static-only review policy needed; do not select previous history"
            )
        review_inputs = {
            "include_scout": True,
            "scout_candidate_ids": [c["id"] for c in full["candidates"]],
            "discover": False,
            "max_steps": 6,
            "max_batches": 100,
            "batch_size": 4,
            "max_context_chars": 40000,
        }
        review = checkpoint_stage(
            directory / "full-review.json",
            lambda audit=audit, review_inputs=review_inputs: stage(
                audit, "review", review_inputs, 48, 1000000, 1200
            ),
            ReviewService,
            build_review_graph,
        )
        summary["projects"].append(
            {
                "project": project,
                "snapshot": record["snapshot"],
                "input_additions": len(record["added_files"]),
                "equal": compact(equal),
                "full": compact(full),
                "review": compact(review),
            }
        )
        save(OUTPUT / "summary.json", summary)
        if (
            snapshot_digest(Path(record["source"])) != record["snapshot"]
            or implementation_hashes() != hashes
        ):
            raise RuntimeError("Input or implementation changed during run")
    save(
        OUTPUT / "integrity.json",
        {
            "input_and_implementation_unchanged": True,
            "gui": False,
            "target_services": False,
        },
    )
    print(
        json.dumps(
            {
                "run_id": OUTPUT.name,
                "projects": [r["project"] for r in summary["projects"]],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
