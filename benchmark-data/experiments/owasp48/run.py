"""Equal-budget genuine platform runs; oracle is never opened by this runner."""

import argparse
import hashlib
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

from scripts.benchmarks.formal_baseline import run_one
from scripts.benchmarks.formal_runtime import checkpoint_stage, register_audit

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "artifacts/research/owasp48/20261007-evolution"


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def read(path):
    return json.loads(path.read_text())


def hashes():
    import app

    path = Path(app.__file__).parent
    return {
        str(p.relative_to(path)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in path.rglob("*")
        if p.is_file() and p.suffix in {".py", ".txt"}
    }


def create_stage(audit, kind, inputs, caps, versions):
    policy = policy_snapshot()
    policy.update(
        max_calls=caps["calls"], max_tokens=caps["tokens"], max_seconds=caps["seconds"]
    )
    with Session(engine) as db:
        stage = StageRun(
            audit_id=UUID(audit),
            kind=kind,
            prompt_version=versions[kind],
            inputs=inputs,
            model_config_snapshot=policy,
        )
        db.add(stage)
        db.commit()
        db.refresh(stage)
        return str(stage.id)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--static-only", action="store_true")
    args = parser.parse_args()
    protocol = read(OUT / "protocol.json")
    material = OUT / "samples" / args.sample
    paths = read(material / "model-batches.json")
    source = Path(paths["source"])
    row = {
        "id": args.sample,
        "source": str(source),
        "language": "python",
        "files": sum(p.is_file() for p in source.rglob("*")),
        "input_regime": "48 anonymous cases with unchanged common helpers/bootstrap/templates",
    }
    save(
        OUT / "inputs.json",
        {
            "records": [
                {
                    **r,
                    "id": r["role"],
                    "language": "python",
                    "files": r["source_files"],
                    "input_regime": row["input_regime"],
                }
                for r in protocol["samples"]
            ]
        },
    )
    static = run_one(row, protocol, 1, output=OUT)
    assert static["status"] == "succeeded", static.get("error")
    if args.static_only:
        return
    save(OUT / "config.json", {"codeql_cli": protocol["codeql_cli"]})
    directory = OUT / "runs" / args.version / args.sample
    config = {
        "production_hashes": hashes(),
        "snapshot": snapshot_digest(source),
        "model_policy": policy_snapshot(),
        "caps": protocol["stage_caps"],
        "concurrency": protocol["concurrency"],
        "input_manifest_sha256": hashlib.sha256(
            (material / "model-batches.json").read_bytes()
        ).hexdigest(),
        "scorer_sha256": protocol["scorer_sha256"],
        "labels_into_model": False,
        "sample": args.sample,
        "version": args.version,
    }
    if (directory / "config.json").exists():
        assert read(directory / "config.json") == config, (
            "Do not resume changed implementation"
        )
    else:
        save(directory / "config.json", config)
    audit = register_audit(args.sample, output=OUT)
    findings = static["rounds"][0]["findings"]
    caps = protocol["stage_caps"]
    versions = (
        {"scout": "6", "review": "8"}
        if args.version == "base"
        else {"scout": "7", "review": "9"}
        if args.version == "revision-01"
        else {"scout": "8", "review": "10"}
    )

    def run_batch(batch):
        target = directory / batch["group_id"]
        scopes = ["app.py", "helpers", *batch["case_paths"]]
        scout = checkpoint_stage(
            target / "scout.json",
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
                caps,
                versions,
            ),
            ScoutService,
            build_scout_graph,
        )
        static_ids = [
            f["id"]
            for f in findings
            if any(
                Path(loc["file"]).name in {Path(p).name for p in batch["case_paths"]}
                for loc in f["locations"]
            )
        ]
        selected = [c["id"] for c in scout["candidates"]]
        review = checkpoint_stage(
            target / "review.json",
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
                caps,
                versions,
            ),
            ReviewService,
            build_review_graph,
        )
        summary = {
            "batch": batch["group_id"],
            "case_paths": batch["case_paths"],
            "scout_stage_id": scout["stage_id"],
            "review_stage_id": review["stage_id"],
            "scout_status": scout["stage"]["status"],
            "review_status": review["stage"]["status"],
            "scout_wall_seconds": scout["wall_seconds"],
            "review_wall_seconds": review["wall_seconds"],
        }
        save(target / "summary.json", summary)
        return summary

    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=protocol["concurrency"]) as pool:
        rows = list(pool.map(run_batch, paths["batches"]))
    save(
        directory / "summary.json",
        {
            "batches": rows,
            "parallel_wall_seconds": time.monotonic() - started,
            "static_seconds_once_shared": static["wall_seconds"],
        },
    )
    assert (
        hashes() == config["production_hashes"]
        and snapshot_digest(source) == config["snapshot"]
    )
    save(
        directory / "integrity.json",
        {"input_and_implementation_unchanged": True, "model_labels": False},
    )


if __name__ == "__main__":
    main()
