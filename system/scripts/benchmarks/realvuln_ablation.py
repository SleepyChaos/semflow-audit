"""Reconstruct existing ablation evidence offline; never synthesize D/E runs."""

import argparse
import json
from collections import Counter
from pathlib import Path

from scripts.benchmarks.realvuln_ablation_io import (
    Evaluator,
    call_resources,
    csv_write,
    findings,
    raw_candidates,
    read,
    sha,
)
from scripts.benchmarks.realvuln_ablation_transitions import transitions
from scripts.benchmarks.realvuln_compare import validate_inputs
from scripts.benchmarks.realvuln_prepare import save
from scripts.benchmarks.realvuln_score import metrics, project_outputs


def catalog(base):
    stages = {}
    for root in sorted(base.glob("20261013-*")):
        for path in (root / "system").glob("*/*.json"):
            if path.name not in {"scout.json", "review.json"}:
                continue
            receipt = read(path)
            stage = receipt["stage"]
            prior = stages.get(stage["id"])
            if prior is None or len(stage.get("model_calls", [])) > len(
                prior["stage"].get("model_calls", [])
            ):
                stages[stage["id"]] = {
                    "stage": stage,
                    "receipt": str(path),
                    "wall_seconds": receipt["wall_seconds"],
                }
    return stages


def inventory(root, project, scout, review, base):
    config = read(root / "config.json")
    receipt = read(root / "acquisition" / f"{project}.json")
    frozen = read(root / "implementation-hashes.json")
    for name, expected in frozen.items():
        if sha(root / "implementation" / name) != expected:
            raise RuntimeError(f"Frozen implementation changed: {root}/{name}")
    from app.adapters.snapshot import snapshot_digest

    if snapshot_digest(root / "sources" / project) != receipt["snapshot"]:
        raise RuntimeError(f"Source snapshot changed: {project}")
    reference = read(base / "20261013-progress-v3-retest/implementation-hashes.json")
    return {
        "project_id": project,
        "selected_run": root.name,
        "snapshot": receipt["snapshot"],
        "codeql_cli": config["codeql_cli"],
        "pack": config["packs"]["python"]["pack"],
        "suite": config["packs"]["python"]["suite"],
        "implementation_hashes": sha(root / "implementation-hashes.json"),
        "implementation_diff_from_v3": [
            p for p in reference if frozen.get(p) != reference[p]
        ],
        "scout_stage_id": scout["stage_id"],
        "scout_lineage": scout.get("candidate_lineage_stage_ids", []),
        "scout_candidate_stage_ids": sorted(
            {c["stage_id"] for c in scout["candidates"]}
        ),
        "review_stage_id": review["stage_id"],
        **{
            f"{kind}_{key}": value
            for kind, record in (("scout", scout), ("review", review))
            for key, value in {
                "prompt_version": record["stage"]["prompt_version"],
                "prompt_hashes": sorted(
                    {
                        c.get("prompt_hash")
                        for c in record["stage"]["model_calls"]
                        if c.get("prompt_hash")
                    }
                ),
                "response_models": sorted(
                    {
                        c.get("response_model")
                        for c in record["stage"]["model_calls"]
                        if c.get("response_model")
                    }
                ),
                "response_model_unknown_calls": sum(
                    not c.get("response_model") for c in record["stage"]["model_calls"]
                ),
                "policy": {
                    k: v
                    for k, v in record["stage"]["model_config_snapshot"].items()
                    if k != "prompt_snapshot"
                },
                "status": record["stage"]["status"],
            }.items()
        },
        "source_and_implementation_verified": True,
    }


def build(base, output):
    output.mkdir(parents=True, exist_ok=True)
    provenance = read(
        base / "20261013-progress-v3-retest/incremental-report-data.json"
    )["provenance"]
    full = base / "20261013-progress-v2"
    for root in {Path(p) for p in provenance.values()}:
        validate_inputs(full, root)
    dataset = read(full / "dataset.json")
    for name, expected in dataset["gold_sha256"].items():
        if (
            "__pycache__" not in Path(name).parts
            and not name.endswith(".pyc")
            and sha(full / "evaluator-only" / name) != expected
        ):
            raise RuntimeError("Evaluator identity changed")
    evaluator, stages = Evaluator(full), catalog(base)
    per_project, overlap, transition_rows, identities, gold_rows = [], [], [], [], []
    cards = {g: [] for g in ("A", "B", "C", "F")}
    selected_ids = {g: set() for g in cards}
    allocation_differences = []
    for project, location in provenance.items():
        root = Path(location)
        scout = read(root / "system" / project / "scout.json")
        review = read(root / "system" / project / "review.json")
        static = read(root / "static" / project / "result.json")
        raw = raw_candidates(static["rounds"][0]["findings"], scout["candidates"])
        source, gold = root / "sources" / project, evaluator.gold(project)
        outputs, status = project_outputs(root, project, source)
        groups = {
            "A": outputs["codeql"],
            "B": findings([r for r in raw if r["source"] == "scout"], "B", source),
            "C": outputs["raw_union"],
            "F": outputs["system_supported"],
        }
        scored = {g: evaluator.score(project, g, fs, gold) for g, fs in groups.items()}
        identities.append(inventory(root, project, scout, review, base))
        lineage = set(scout.get("candidate_lineage_stage_ids", [])) | {
            scout["stage_id"]
        }
        lineage |= {c["stage_id"] for c in scout["candidates"]}
        for g in ("B", "C", "F"):
            selected_ids[g].update(lineage)
        selected_ids["F"].add(review["stage_id"])
        coverage = scout["stage"]["result"].get("coverage", {})
        for g, (card, *_) in scored.items():
            cards[g].append(card)
            used = (
                lineage | ({review["stage_id"]} if g == "F" else set())
                if g != "A"
                else set()
            )
            resources = [call_resources(stages[i]["stage"]) for i in used]
            per_project.append(
                {
                    "group": g,
                    "project_id": project,
                    **{
                        k: card[k]
                        for k in (
                            "tp",
                            "fp",
                            "fn",
                            "tn",
                            "precision",
                            "recall",
                            "f1",
                            "f3",
                        )
                    },
                    "status": static["status"]
                    if g == "A"
                    else scout["stage"]["status"]
                    if g in {"B", "C"}
                    else status["system_status"],
                    "gold_vulnerabilities": card["tp"] + card["fn"],
                    "calls_reused": sum(r["calls"] for r in resources),
                    "input_tokens_known": sum(r["input_tokens"] for r in resources),
                    "output_tokens_known": sum(r["output_tokens"] for r in resources),
                    "unknown_usage_calls": sum(
                        r["unknown_usage_calls"] for r in resources
                    ),
                    "calls_new": 0,
                    "window_inspected": coverage.get(
                        "inspected_eligible_windows", coverage.get("inspected_windows")
                    )
                    if g != "A"
                    else None,
                    "window_eligible": coverage.get("eligible_windows")
                    if g != "A"
                    else None,
                    "candidate_states": dict(
                        Counter(c["model_assessment"] for c in review["candidates"])
                    )
                    if g == "F"
                    else {},
                    "adopted_stage_ids": sorted(used),
                    "wall_seconds_adopted": sum(stages[i]["wall_seconds"] for i in used)
                    + (static["wall_seconds"] if g != "B" else 0),
                    "receipt": str(root / "system" / project),
                }
            )
        a, b, c, f = (scored[g][1] for g in ("A", "B", "C", "F"))
        if a | b != c:
            allocation_differences.append(
                {
                    "project_id": project,
                    "independent_union": sorted(a | b),
                    "group_C": sorted(c),
                    "C_only": sorted(c - (a | b)),
                    "independent_only": sorted((a | b) - c),
                }
            )
        project_transitions = transitions(
            project, root, raw, review, scored, evaluator, gold, source
        )
        transition_rows.extend(project_transitions)
        for label in gold["findings"]:
            if not label["is_vulnerable"]:
                continue
            identifier = label["id"]
            compatible = {
                engine: [
                    r["id"]
                    for r in raw
                    if r["source"] == engine
                    and identifier in scored["C"][3].get(r["id"], [])
                ]
                for engine in ("codeql", "scout")
            }
            overlap.append(
                {
                    "project_id": project,
                    "gold_id": identifier,
                    "codeql_independent_hit": identifier in a,
                    "scout_independent_hit": identifier in b,
                    "C_union_hit": identifier in c,
                    "codeql_compatible_candidates": compatible["codeql"],
                    "scout_compatible_candidates": compatible["scout"],
                    "match_basis": "official matcher: file/acceptable location, acceptable CWE, ±10 lines; greedy one-use gold allocation",
                }
            )
            related = [
                r
                for r in project_transitions
                if identifier in r.get("before_compatible_gold_ids", [])
            ]
            gold_rows.append(
                {
                    "group": "F",
                    "project_id": project,
                    "gold_id": identifier,
                    "before_C_hit": identifier in c,
                    "after_supported_hit": identifier in f,
                    "transition": "retained"
                    if identifier in c & f
                    else "lost_from_supported"
                    if identifier in c
                    else "gained_after_review"
                    if identifier in f
                    else "missed_both",
                    "related_candidate_states": dict(
                        Counter(r["review_state"] for r in related)
                    ),
                    "candidate_ids": [r["candidate_id"] for r in related],
                    "reasons": [r.get("reason") for r in related if r.get("reason")],
                    "scoring_change_possible": any(
                        r.get("cwe_changed") or r.get("location_changed")
                        for r in related
                    ),
                }
            )
        for g in ("D", "E"):
            per_project.append(
                {
                    "group": g,
                    "project_id": project,
                    "status": "not_run_independent_review",
                    "gold_vulnerabilities": len(a) + scored["A"][0]["fn"],
                    "calls_new": 0,
                    "receipt": None,
                }
            )
    summary = []
    for g in "ABCDEF":
        resources = [
            call_resources(stages[i]["stage"]) for i in selected_ids.get(g, set())
        ]
        summary.append(
            {
                "group": g,
                "status": "historical_incremental_rescore_not_uniform_v3"
                if g in cards
                else "not_run_independent_review",
                **(metrics(cards[g]) if g in cards else {}),
                "projects_frozen": 26,
                "projects_scored": 26 if g in cards else 0,
                "gold_vulnerabilities": 676,
                "calls_new": 0,
                "calls_reused": sum(r["calls"] for r in resources),
                "input_tokens_known": sum(r["input_tokens"] for r in resources),
                "output_tokens_known": sum(r["output_tokens"] for r in resources),
                "unknown_usage_calls": sum(r["unknown_usage_calls"] for r in resources),
            }
        )
    for name, rows in (
        ("ablation-summary.csv", summary),
        ("ablation-per-project.csv", per_project),
        ("discovery-overlap.csv", overlap),
        ("review-transitions.csv", transition_rows),
        ("review-gold-transitions.csv", gold_rows),
        ("stage-inventory.csv", identities),
    ):
        csv_write(
            output / name,
            rows,
            display_metrics=name
            in {"ablation-summary.csv", "ablation-per-project.csv"},
        )
    save(
        output / "ablation-data.json",
        {
            "summary": summary,
            "inventory": identities,
            "allocation_differences": allocation_differences,
            "gold_transitions": dict(Counter(r["transition"] for r in gold_rows)),
            "candidate_transitions": dict(
                Counter(r["review_state"] for r in transition_rows)
            ),
            "all_attempt_resources_unique_stages": {
                k: sum(call_resources(v["stage"])[k] for v in stages.values())
                for k in (
                    "calls",
                    "input_tokens",
                    "output_tokens",
                    "unknown_usage_calls",
                )
            },
            "selected_stage_ids": {g: sorted(ids) for g, ids in selected_ids.items()},
            "new_model_calls": 0,
        },
    )
    save(output / "all-attempt-stage-ledger.json", stages)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build(args.base.resolve(), args.output.resolve())


if __name__ == "__main__":
    main()
