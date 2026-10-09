"""Paired review of immutable old pools; separately test expanded coverage and scout."""

import hashlib
import json
from pathlib import Path

from app.adapters.ai.policy import policy_snapshot
from app.adapters.snapshot import snapshot_digest
from app.core.db import engine
from app.persistence.stage_models import StageRun
from app.services.review import ReviewService
from app.services.scouting import ScoutService
from app.workflows.review import build_review_graph
from app.workflows.scouting import build_scout_graph
from sqlmodel import Session

from scripts.benchmarks.formal_freeze import OUTPUT as PREVIOUS
from scripts.benchmarks.formal_freeze import ROOT, save
from scripts.benchmarks.formal_runtime import checkpoint_stage, register_audit

OUTPUT = ROOT / "artifacts/research/discovery-retest/20261005-v2"


def stage(audit, kind, version, inputs, calls=12):
    policy = policy_snapshot()
    policy.update(max_calls=calls, max_seconds=240 if calls == 12 else 300)
    if calls == 24:
        policy["max_tokens"] = 200000
    with Session(engine) as db:
        row = StageRun(
            audit_id=audit,
            kind=kind,
            prompt_version=version,
            inputs=inputs,
            model_config_snapshot=policy,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return str(row.id)


def reviewed_summary(row, project, old):
    result = row["stage"]["result"]
    entries = result.get("pool", {}).get("entries", [])
    roots = {r["gold_id"]: r for r in old["roots"]}
    mappings = {}
    for entry in entries:
        matches = [
            identifier
            for identifier, root in roots.items()
            if (
                entry.get("static_alert", {}).get("id") in root["static_ids"]
                if entry["origin"] == "static"
                else entry.get("source_candidate_id") in root["scout_ids"]
            )
        ]
        mappings[entry["candidate_id"]] = matches
    # Primary-condition policy used by the original report; debug was a bundled secondary.
    secondary = {"damn-vulnerable-flask-app-011"} if project == "rv-flask" else set()
    static = {
        i
        for i, root in roots.items()
        if root["static_ids"] and root["gold_is_vulnerable"]
    }
    matched = {
        name: set() for name in ("supported", "excluded", "insufficient", "pending")
    }
    unsupported = []
    for recommendation in result.get("recommendations", []):
        ids = mappings.get(recommendation["id"], [])
        matched[recommendation["recommendation"]].update(ids)
        if not ids:
            unsupported.append(recommendation)
    positives = {i for i, r in roots.items() if r["gold_is_vulnerable"]} - secondary
    false = {i for i, r in roots.items() if not r["gold_is_vulnerable"]}
    return {
        "project": project,
        "stage_status": row["stage"]["status"],
        "stage_error": row["stage"].get("error"),
        "wall_seconds": row["wall_seconds"],
        "usage": row["stage"]["usage"],
        "candidate_count": len(entries),
        "reviewed_candidates": len(
            {r["id"] for r in result.get("recommendations", [])} & set(mappings)
        ),
        "unreviewed_candidates": len(result.get("unreviewed_candidate_ids", [])),
        "coverage": result.get("coverage_status"),
        "schedule": result.get("schedule"),
        "verdict_counts": {
            name: sum(
                r["recommendation"] == name for r in result.get("recommendations", [])
            )
            for name in matched
        },
        "supported_positive_roots": sorted(matched["supported"] & positives),
        "additional_supported_roots": sorted(
            (matched["supported"] & positives) - static
        ),
        "supported_false_traps": sorted(matched["supported"] & false),
        "excluded_positive_roots": sorted(matched["excluded"] & positives),
        "excluded_false_traps": sorted(matched["excluded"] & false),
        "unmapped_recommendations": unsupported,
        "incomplete_batches": [
            r for r in result.get("batches", []) if r["status"] != "completed"
        ],
        "adjudication": "same old provisional root associations; not human gold or exploit validation",
    }


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    config = OUTPUT / "config.json"
    identities = {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for folder in ("backend/app", "scripts/benchmarks")
        for p in (ROOT / folder).rglob("*")
        if p.is_file() and p.suffix in {".py", ".txt"}
    }
    if config.exists():
        if json.loads(config.read_text())["implementation_hashes"] != identities:
            raise RuntimeError("Retest implementation changed; create new run ID")
    else:
        save(
            config,
            {
                "implementation_hashes": identities,
                "previous_run": PREVIOUS.name,
                "paired_review_max_calls": 12,
                "coverage_review_max_calls": 24,
                "gui": False,
                "target_services": False,
                "note": "Same immutable old pools; review6 source boundary, 8192 output cap, coverage scheduling, no supplementary findings. Additional 24-call/200K-token run is sensitivity, not equal-budget improvement",
            },
        )
    adjudication = json.loads(
        (PREVIOUS / "discovery/root-adjudication.json").read_text()
    )
    summary = {"run_id": OUTPUT.name, "paired": [], "expanded": [], "scout": []}
    for project in ("rv-flask", "rv-dvna"):
        audit = register_audit(project)
        original = json.loads(
            (PREVIOUS / "discovery" / project / "D1.json").read_text()
        )
        baseline = json.loads(
            (PREVIOUS / "static" / project / "result.json").read_text()
        )
        input_record = next(
            r
            for r in json.loads((PREVIOUS / "inputs.json").read_text())["records"]
            if r["id"] == project
        )
        if snapshot_digest(Path(input_record["source"])) != baseline["snapshot"]:
            raise RuntimeError("Original input changed")
        selected = [r["id"] for r in original["candidates"]]
        inputs = {
            "include_scout": True,
            "discover": False,
            "scout_candidate_ids": selected,
            "max_steps": 6,
            "max_batches": 24,
            "batch_size": 4,
        }
        gold = next(r for r in adjudication["projects"] if r["project"] == project)
        directory = OUTPUT / project
        for name, calls in (("paired-12", 12), ("coverage-24", 24)):
            row = checkpoint_stage(
                directory / (name + ".json"),
                lambda calls=calls, audit=audit, inputs=inputs: stage(
                    audit, "review", "6", inputs, calls
                ),
                ReviewService,
                build_review_graph,
            )
            scored = reviewed_summary(row, project, gold)
            save(directory / (name + "-scored.json"), scored)
            summary["paired" if calls == 12 else "expanded"].append(scored)
            if (
                scored["stage_status"] == "completed"
                and scored["coverage"] == "completed"
            ):
                break
        scout = checkpoint_stage(
            directory / "scout-v3.json",
            lambda audit=audit: stage(
                audit,
                "scout",
                "3",
                {
                    "max_units": 8,
                    "steps_per_unit": 3,
                    "window_lines": 100,
                    "max_context_chars": 30000,
                },
            ),
            ScoutService,
            build_scout_graph,
        )
        summary["scout"].append(
            {
                "project": project,
                "stage_id": scout["stage_id"],
                "status": scout["stage"]["status"],
                "usage": scout["stage"]["usage"],
                "candidate_count": len(scout["candidates"]),
                "wall_seconds": scout["wall_seconds"],
                "coverage": scout["stage"]["result"].get("coverage"),
            }
        )
        save(OUTPUT / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
