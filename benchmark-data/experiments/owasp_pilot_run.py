"""Frozen scoped representative OWASP pilot; model path list has no hidden labels."""

import json
import time
from concurrent.futures import ThreadPoolExecutor
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

from scripts.benchmarks.discovery_coverage_retest import compact, implementation_hashes
from scripts.benchmarks.formal_freeze import OUTPUT as STATIC
from scripts.benchmarks.formal_freeze import ROOT, save
from scripts.benchmarks.formal_runtime import checkpoint_stage, register_audit

PREP = ROOT / "artifacts/research/owasp-discovery/20261007-pilot-preparation"
OUTPUT = ROOT / "artifacts/research/owasp-discovery/20261007-pilot-v1"


def create_stage(audit, kind, inputs):
    policy = policy_snapshot()
    policy.update(max_calls=28, max_tokens=500000, max_seconds=600)
    with Session(engine) as db:
        row = StageRun(
            audit_id=UUID(audit),
            kind=kind,
            prompt_version="6" if kind == "scout" else "8",
            inputs=inputs,
            model_config_snapshot=policy,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return str(row.id)


def main():
    paths = json.loads((PREP / "model-batches.json").read_text())
    source = Path(paths["source"])
    hashes = implementation_hashes()
    baseline = json.loads(
        (STATIC / "static/owasp-python-loader-fixed/result.json").read_text()
    )
    assert (
        baseline["status"] == "succeeded"
        and snapshot_digest(source) == baseline["snapshot"]
    )
    import hashlib

    config = {
        "implementation_hashes": hashes,
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "model_batches_sha256": hashlib.sha256(
            (PREP / "model-batches.json").read_bytes()
        ).hexdigest(),
        "snapshot": baseline["snapshot"],
        "scout": "6",
        "review": "8",
        "per_stage_caps": {"calls": 28, "tokens": 500000, "seconds": 600},
        "concurrency": 3,
        "input_regime": "Selected anonymous testcases plus complete app/bootstrap/helpers; original full snapshot static reuse. Source subset pilot, not full-project AI coverage.",
        "gui": False,
        "target_services": False,
        "labels_into_model": False,
    }
    p = OUTPUT / "config.json"
    if p.exists():
        assert json.loads(p.read_text()) == config
    else:
        save(p, config)
    audit = register_audit("owasp-python-loader-fixed", output=STATIC)
    findings = baseline["rounds"][0]["findings"]

    def run_batch(batch):
        directory = OUTPUT / batch["group_id"]
        scopes = ["app.py", "helpers", *batch["case_paths"]]
        scout = checkpoint_stage(
            directory / "scout.json",
            lambda: create_stage(
                audit,
                "scout",
                {
                    "paths": scopes,
                    "inspection_paths": ["app.py", *batch["case_paths"]],
                    "max_units": 24,
                    "steps_per_unit": 2,
                    "window_lines": 100,
                    "max_context_chars": 34000,
                },
            ),
            ScoutService,
            build_scout_graph,
        )
        static_ids = [
            f["id"]
            for f in findings
            if any(loc["file"] in batch["case_paths"] for loc in f["locations"])
        ]
        # Explicit IDs; no use of positive/negative oracle or intended CWE to choose alerts.
        selected = [c["id"] for c in scout["candidates"]]
        review = checkpoint_stage(
            directory / "review.json",
            lambda: create_stage(
                audit,
                "review",
                {
                    "paths": scopes,
                    "finding_ids": static_ids,
                    "include_scout": bool(selected),
                    "scout_candidate_ids": selected,
                    "discover": False,
                    "batch_size": 4,
                    "max_batches": 24,
                    "max_steps": 4,
                    "max_context_chars": 40000,
                },
            ),
            ReviewService,
            build_review_graph,
        )
        row = {
            "batch": batch["group_id"],
            "case_paths": batch["case_paths"],
            "scout": compact(scout),
            "review": compact(review),
        }
        save(directory / "summary.json", row)
        return row

    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=3) as pool:
        rows = list(pool.map(run_batch, paths["batches"]))
    save(OUTPUT / "summary.json", {"batches": rows, "actual_parallel_wall_seconds": time.monotonic() - started})
    assert (
        implementation_hashes() == hashes
        and snapshot_digest(source) == baseline["snapshot"]
    )
    save(
        OUTPUT / "integrity.json",
        {
            "input_and_implementation_unchanged": True,
            "labels_into_model": False,
            "gui": False,
            "target_services": False,
        },
    )


if __name__ == "__main__":
    main()
