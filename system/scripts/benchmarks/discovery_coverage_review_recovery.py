"""One bounded retry of unreviewed candidates only, plus one static control."""

import json

from app.services.review import ReviewService
from app.workflows.review import build_review_graph

from scripts.benchmarks.discovery_coverage_retest import (
    compact,
    implementation_hashes,
    stage,
)
from scripts.benchmarks.formal_freeze import ROOT, save
from scripts.benchmarks.formal_runtime import checkpoint_stage

PREVIOUS = ROOT / "artifacts/research/discovery-coverage/20261006-v5"
OUTPUT = ROOT / "artifacts/research/discovery-coverage/20261006-v6"


def main():
    hashes = implementation_hashes()
    config = {
        "implementation_hashes": hashes,
        "previous_run": PREVIOUS.name,
        "reason": "One incomplete cohort: cross-file counterevidence omitted target source citation",
        "scope": "Unreviewed Scout identities only, one positive static control, no gold feedback",
        "calls": 12,
        "tokens": 200000,
        "seconds": 300,
        "batch_size": 1,
        "retry_limit": 1,
        "gui": False,
        "target_services": False,
    }
    path = OUTPUT / "config.json"
    if path.exists() and json.loads(path.read_text()) != config:
        raise RuntimeError("Recovery changed; new run ID required")
    save(path, config)
    previous = json.loads((PREVIOUS / "rv-dvna/full-review.json").read_text())
    result = previous["stage"]["result"]
    incomplete = set(result["unreviewed_candidate_ids"])
    entries = result["pool"]["entries"]
    selected = [
        p["source_candidate_id"]
        for p in entries
        if p["candidate_id"] in incomplete and p["origin"] == "scout"
    ]
    if len(selected) != len(incomplete) or not selected:
        raise RuntimeError("Recovery scope changed")
    # finding_ids=[] means all static findings in the production API. Select one
    # already assessed alert as an explicit control, retaining unrestricted source
    # tools. It is a duplicate control, not an additional detection or a gold hint.
    control = next(p for p in entries if p["origin"] == "static")
    inputs = {
        "include_scout": True,
        "scout_candidate_ids": selected,
        "finding_ids": [control["static_alert"]["id"]],
        "discover": False,
        "max_steps": 4,
        "max_batches": 10,
        "batch_size": 1,
        "max_context_chars": 40000,
    }
    recovery = checkpoint_stage(
        OUTPUT / "rv-dvna/review-recovery.json",
        lambda: stage(
            previous["stage"]["audit_id"], "review", inputs,
            12, 200000, 300, review_version="7",
        ),
        ReviewService,
        build_review_graph,
    )
    save(OUTPUT / "summary.json", {
        "run_id": OUTPUT.name,
        "original_review_stage": previous["stage_id"],
        "original_unreviewed_ids": sorted(incomplete),
        "scout_candidate_ids": selected,
        "duplicate_static_control": control["static_alert"]["id"],
        "review": compact(recovery),
        "original_result_preserved": True,
    })
    if implementation_hashes() != hashes:
        raise RuntimeError("Recovery implementation changed")
    save(OUTPUT / "integrity.json", {
        "implementation_unchanged": True,
        "single_retry_only": True,
        "whole_pool_not_repeated": True,
    })


if __name__ == "__main__":
    main()
