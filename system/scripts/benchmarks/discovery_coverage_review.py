"""Review7 on the exact completed Scout5 pools, without repeating source scanning."""

import json
from pathlib import Path

from app.adapters.snapshot import snapshot_digest
from app.services.review import ReviewService
from app.workflows.review import build_review_graph

from scripts.benchmarks.discovery_coverage_retest import (
    compact,
    implementation_hashes,
    stage,
)
from scripts.benchmarks.formal_freeze import ROOT, save
from scripts.benchmarks.formal_runtime import checkpoint_stage, register_audit

INPUT_RUN = ROOT / "artifacts/research/discovery-coverage/20261006-v2"
RECOVERY_RUN = ROOT / "artifacts/research/discovery-coverage/20261006-v3"
PREVIOUS_REVIEW = ROOT / "artifacts/research/discovery-coverage/20261006-v4"
OUTPUT = ROOT / "artifacts/research/discovery-coverage/20261006-v5"


def main():
    hashes = implementation_hashes()
    rows = json.loads((INPUT_RUN / "inputs.json").read_text())["records"]
    config = {
        "implementation_hashes": hashes,
        "reused_scouts": INPUT_RUN.name,
        "reused_recovery": RECOVERY_RUN.name,
        "reused_completed_review": PREVIOUS_REVIEW.name,
        "runner_correction": "Exclude metadata-only .started.json recovery receipts",
        "review_version": "7",
        "calls": 48,
        "tokens": 1000000,
        "seconds": 1200,
        "gui": False,
        "target_services": False,
    }
    path = OUTPUT / "config.json"
    if path.exists() and json.loads(path.read_text()) != config:
        raise RuntimeError("Review7 run changed; create new run ID")
    save(path, config)
    summary = {"run_id": OUTPUT.name, "projects": []}
    for record in rows:
        project = record["id"]
        if snapshot_digest(Path(record["source"])) != record["snapshot"]:
            raise RuntimeError("Reused input changed")
        scout = json.loads((INPUT_RUN / project / "full-scout.json").read_text())
        selected = [c["id"] for c in scout["candidates"]]
        for p in (RECOVERY_RUN / project).glob("recover-*.json"):
            if p.name.endswith(".started.json"):
                continue
            selected += [c["id"] for c in json.loads(p.read_text())["candidates"]]
        audit = register_audit(project, output=INPUT_RUN)
        inputs = {
            "include_scout": True,
            "scout_candidate_ids": selected,
            "discover": False,
            "max_steps": 6,
            "max_batches": 100,
            "batch_size": 4,
            "max_context_chars": 40000,
        }
        previous = PREVIOUS_REVIEW / project / "full-review.json"
        destination = OUTPUT / project / "full-review.json"
        if previous.exists() and not destination.exists():
            prior = json.loads(previous.read_text())
            if (
                prior["stage"]["status"] != "completed"
                or prior["stage"]["prompt_version"] != "7"
                or prior["stage"]["inputs"] != inputs
                or prior["stage"]["audit_id"] != audit
            ):
                raise RuntimeError("Previous review does not match reused pool")
            previous_hashes = json.loads(
                (PREVIOUS_REVIEW / "config.json").read_text()
            )["implementation_hashes"]
            for name, digest in hashes.items():
                if name.startswith("system/backend/") and previous_hashes.get(name) != digest:
                    raise RuntimeError("Production implementation differs from previous review")
            save(destination, prior)
            save(OUTPUT / project / "reused-review.json", {
                "source": str(previous.relative_to(ROOT)),
                "stage_id": prior["stage_id"],
                "production_implementation_unchanged": True,
                "new_model_calls": 0,
            })
        result = checkpoint_stage(
            destination,
            lambda audit=audit, inputs=inputs: stage(
                audit, "review", inputs, 48, 1000000, 1200, review_version="7"
            ),
            ReviewService,
            build_review_graph,
        )
        summary["projects"].append(
            {
                "project": project,
                "snapshot": record["snapshot"],
                "review": compact(result),
            }
        )
        save(OUTPUT / "summary.json", summary)
        if implementation_hashes() != hashes:
            raise RuntimeError("Review7 implementation changed")
    save(
        OUTPUT / "integrity.json",
        {
            "input_and_implementation_unchanged": True,
            "gui": False,
            "target_services": False,
            "paid_scouts_preserved_and_reused": True,
        },
    )
    print(
        json.dumps(
            {
                "run_id": OUTPUT.name,
                "projects": [r["project"] for r in summary["projects"]],
            }
        )
    )


if __name__ == "__main__":
    main()
