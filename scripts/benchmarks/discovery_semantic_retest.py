"""Frozen Review8 paired pool and source-driven Scout6 supplementation, no gold input."""

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

BASE = ROOT / "artifacts/research/discovery-coverage/20261006-v2"
RECOVERY = ROOT / "artifacts/research/discovery-coverage/20261006-v3"
OUTPUT = ROOT / "artifacts/research/discovery-semantics/20261007-v3"


def main():
    hashes = implementation_hashes()
    config = {
        "implementation_hashes": hashes,
        "scout_version": "6",
        "review_version": "8",
        "paired_review": "Prior v2 same-pool diagnostic retained separately; no repeated paid paired stage in v3",
        "source_supplement": {"calls": 96, "tokens": 1200000, "seconds": 1200},
        "combined_review": {"calls": 96, "tokens": 2000000, "seconds": 1800},
        "selection": "All Python/JS implementation modules and readable config, independent of gold; existing template Scout5 hypotheses reused",
        "labels_into_model": False,
        "gui": False,
        "target_services": False,
    }
    p = OUTPUT / "config.json"
    if p.exists() and json.loads(p.read_text()) != config:
        raise RuntimeError("Frozen implementation changed; create new run ID")
    save(p, config)
    summary = {"run_id": OUTPUT.name, "projects": []}
    for record in json.loads((BASE / "inputs.json").read_text())["records"]:
        project = record["id"]
        if snapshot_digest(Path(record["source"])) != record["snapshot"]:
            raise RuntimeError("Input changed")
        audit = register_audit(project, output=BASE)
        old = json.loads((BASE / project / "full-scout.json").read_text())
        selected = [c["id"] for c in old["candidates"]]
        for p in (RECOVERY / project).glob("recover-*.json"):
            if not p.name.endswith(".started.json"):
                selected += [c["id"] for c in json.loads(p.read_text())["candidates"]]
        review_inputs = {
            "include_scout": True,
            "scout_candidate_ids": selected,
            "discover": False,
            "max_steps": 6,
            "max_batches": 100,
            "batch_size": 4,
            "max_context_chars": 40000,
        }
        # Paths enumerate all application implementation/config files, not missed gold roots.
        root = Path(record["source"])
        paths = [
            p.relative_to(root).as_posix()
            for p in sorted(root.rglob("*"))
            if p.is_file()
            and p.suffix
            in {".py", ".js", ".jsx", ".ts", ".tsx", ".json", ".yaml", ".yml"}
            and not p.name.endswith(".min.js")
        ]
        from app.adapters.source_inventory import inspectable

        paths = [p for p in paths if inspectable(p, record["language"])]
        inputs = {
            "paths": paths,
            "max_units": 100,
            "steps_per_unit": 3,
            "window_lines": 100,
            "max_context_chars": 34000,
            "include_third_party": False,
        }

        # stage() retains old Scout5 default for old runners; override version before use.
        def create_scout(audit=audit, inputs=inputs):
            from uuid import UUID

            from app.adapters.ai.policy import policy_snapshot
            from app.core.db import engine
            from app.persistence.stage_models import StageRun
            from sqlmodel import Session

            policy = policy_snapshot()
            policy.update(max_calls=96, max_tokens=1200000, max_seconds=1200)
            with Session(engine) as db:
                row = StageRun(
                    audit_id=UUID(audit),
                    kind="scout",
                    prompt_version="6",
                    inputs=inputs,
                    model_config_snapshot=policy,
                )
                db.add(row)
                db.commit()
                db.refresh(row)
                return str(row.id)

        scout = checkpoint_stage(
            OUTPUT / project / "source-scout.json",
            create_scout,
            ScoutService,
            build_scout_graph,
        )
        combined_inputs = {
            **review_inputs,
            "scout_candidate_ids": list(
                dict.fromkeys(selected + [c["id"] for c in scout["candidates"]])
            ),
        }
        combined = checkpoint_stage(
            OUTPUT / project / "combined-review.json",
            lambda audit=audit, combined_inputs=combined_inputs: stage(
                audit, "review", combined_inputs, 96, 2000000, 1800, review_version="8"
            ),
            ReviewService,
            build_review_graph,
        )
        summary["projects"].append(
            {
                "project": project,
                "snapshot": record["snapshot"],
                "source_scout": compact(scout),
                "combined_review": compact(combined),
            }
        )
        save(OUTPUT / "summary.json", summary)
        if (
            implementation_hashes() != hashes
            or snapshot_digest(root) != record["snapshot"]
        ):
            raise RuntimeError("Implementation or source changed during run")
    save(
        OUTPUT / "integrity.json",
        {"inputs_and_implementation_unchanged": True, "labels_into_model": False},
    )


if __name__ == "__main__":
    main()
