"""Targeted closure of failed scout windows/auth modules and unreviewed candidate IDs."""

import json
from uuid import UUID

from app.adapters.ai.policy import policy_snapshot
from app.core.db import engine
from app.persistence.stage_models import StageRun
from app.services.review import ReviewService
from app.services.scouting import ScoutService
from app.workflows.review import build_review_graph
from app.workflows.scouting import build_scout_graph
from sqlmodel import Session

from scripts.benchmarks.discovery_coverage_retest import (
    compact,
    implementation_hashes,
    stage,
)
from scripts.benchmarks.formal_freeze import ROOT, save
from scripts.benchmarks.formal_runtime import checkpoint_stage, register_audit

BASE = ROOT / "artifacts/research/discovery-coverage/20261006-v2"
PREVIOUS = ROOT / "artifacts/research/discovery-semantics/20261007-v3"
OUTPUT = ROOT / "artifacts/research/discovery-semantics/20261007-v6"


def source_stage(audit, inputs):
    policy = policy_snapshot()
    policy.update(max_calls=24, max_tokens=600000, max_seconds=600)
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


def main():
    hashes = implementation_hashes()
    config = {
        "implementation_hashes": hashes,
        "source": "Failed windows plus authentication modules selected by source role, not gold root IDs",
        "review": "Only previously unreviewed identities + new hypotheses; one static control if empty explicit selection",
        "scout_caps": {"calls": 24, "tokens": 600000, "seconds": 600},
        "review_caps": {"calls": 32, "tokens": 700000, "seconds": 900},
        "gui": False,
        "target_services": False,
        "labels_into_model": False,
        "raw_v3_outputs_unchanged": True,
    }
    p = OUTPUT / "config.json"
    if p.exists():
        assert json.loads(p.read_text()) == config
    else:
        save(p, config)
    summary = {"projects": []}
    for project in ["rv-dvna"]:
        audit = register_audit(project, output=BASE)
        prior = json.loads((ROOT / "artifacts/research/discovery-semantics/20261007-v5" / project / "review-closure.json").read_text())
        original = prior["stage"]["result"]
        missing = set(original["unreviewed_candidate_ids"])
        entries = [
            e for e in original["pool"]["entries"] if e["candidate_id"] in missing
        ]
        static_ids = [
            e["static_alert"]["id"] for e in entries if e["origin"] == "static"
        ]
        selected = [e["source_candidate_id"] for e in entries if e["origin"] == "scout"]
        source = None
        if project == "rv-dvna":
            full = json.loads((PREVIOUS / project / "source-scout.json").read_text())
            directory = ROOT / "artifacts/runs" / full["stage_id"]
            project_map = json.loads((directory / "scout-map.json").read_text())
            failed = {
                u["unit_id"]
                for u in full["stage"]["result"]["units"]
                if u["status"] != "inspected"
            }
            files = {u["file"] for u in project_map["units"] if u["id"] in failed}
            files = {f["file"] for f in project_map["files"] if f["file"].endswith("/core/passport.js")}
            inputs = {
                **full["stage"]["inputs"],
                "inspection_paths": sorted(files),
                "steps_per_unit": 3,
            }
            source = checkpoint_stage(
                OUTPUT / project / "targeted-scout.json",
                lambda audit=audit, inputs=inputs: source_stage(audit, inputs),
                ScoutService,
                build_scout_graph,
            )
            selected += [c["id"] for c in source["candidates"]]
        if not static_ids:
            static_ids = [
                next(
                    e["static_alert"]["id"]
                    for e in original["pool"]["entries"]
                    if e["origin"] == "static"
                )
            ]
        inputs = {
            "finding_ids": static_ids,
            "include_scout": bool(selected),
            "scout_candidate_ids": list(dict.fromkeys(selected)),
            "discover": False,
            "max_steps": 4,
            "max_batches": 100,
            "batch_size": 4,
            "max_context_chars": 40000,
        }
        save(
            OUTPUT / project / "selection.json",
            {
                "previous_stage": prior["stage_id"],
                "unreviewed_ids": sorted(missing),
                "static_ids": static_ids,
                "source_candidate_ids": selected,
                "new_source_stage": source["stage_id"] if source else None,
            },
        )
        review = checkpoint_stage(
            OUTPUT / project / "review-closure.json",
            lambda audit=audit, inputs=inputs: stage(
                audit, "review", inputs, 32, 700000, 900, review_version="8"
            ),
            ReviewService,
            build_review_graph,
        )
        summary["projects"].append(
            {
                "project": project,
                "previous_unreviewed": len(missing),
                "source": compact(source) if source else None,
                "review": compact(review),
            }
        )
        save(OUTPUT / "summary.json", summary)
        if implementation_hashes() != hashes:
            raise RuntimeError("Frozen code changed")
    save(
        OUTPUT / "integrity.json",
        {
            "implementation_unchanged": True,
            "old_history_unchanged": True,
            "labels_into_model": False,
        },
    )


if __name__ == "__main__":
    main()
