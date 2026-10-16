"""Sequential full repair performance run; invalid oracles remain unscored."""

import argparse
import json
from collections import Counter
from pathlib import Path

from scripts.benchmarks.mechanical_pipeline import save
from scripts.benchmarks.vul4py_repair import run


def summarize(root, identities):
    rows, times, calls, inputs, outputs = [], [], 0, 0, 0
    for identity in identities:
        folder = root / "runs" / identity
        if (folder / "result.json").exists():
            rows.append(json.loads((folder / "result.json").read_text()))
        if (folder / "generation.json").exists():
            generation = json.loads((folder / "generation.json").read_text())
            times.append(generation["wall_seconds"])
            usage = generation["stage"]["usage"]
            calls += usage.get("calls", 0)
            inputs += usage.get("input_tokens", 0)
            outputs += usage.get("output_tokens", 0)
    ordered = sorted(times)
    return {
        "planned": len(identities),
        "terminal": len(rows),
        "actual_model_stages": len(times),
        "status_counts": dict(Counter(row["status"] for row in rows)),
        "oracle_eligible": sum(row.get("oracle_eligible", False) for row in rows),
        "scored": sum(row["status"] == "evaluated" for row in rows),
        "joint_pass": sum(row.get("joint_pass") is True for row in rows),
        "repair_stage_seconds_total": sum(times),
        "repair_stage_seconds_max": max(times, default=None),
        "repair_stage_seconds_p50": ordered[(len(ordered) - 1) // 2]
        if ordered
        else None,
        "repair_stage_seconds_p95": ordered[(95 * len(ordered) + 99) // 100 - 1]
        if ordered
        else None,
        "calls": calls,
        "input_tokens": inputs,
        "output_tokens": outputs,
        "cases": rows,
        "scope": "100 known-location production repairs, sequential; uncalibrated oracle cannot score; not discovery or human confirmation",
    }


def execute(root):
    identities = [
        row["vuln_id"]
        for row in json.loads((root / "manifest.json").read_text())["cases"]
    ]
    if len(identities) != 100 or len(set(identities)) != 100:
        raise RuntimeError("Expected exactly 100 frozen unique tasks")
    config = json.loads((root / "repair-config.json").read_text())
    if not config.get("generate_uncalibrated"):
        raise RuntimeError(
            "Full performance run requires explicit frozen all-generation policy"
        )
    for identity in identities:
        run(identity, root, config["policy"], config["image_id"])
        summary = summarize(root, identities)
        save(root / "performance-progress.json", summary)
        generation = root / "runs" / identity / "generation.json"
        if generation.exists():
            calls = json.loads(generation.read_text())["stage"].get("model_calls", [])
            if calls and calls[-1].get("error_code") in {
                "provider_error",
                "rate_limited",
                "timeout",
            }:
                save(
                    root / "pipeline-status.json",
                    {"status": "provider_interrupted", "case": identity},
                )
                raise RuntimeError(
                    "Provider interrupted; receipts retained, no blind paid retry"
                )
    save(root / "repair-summary.json", summarize(root, identities))
    save(root / "pipeline-status.json", {"status": "finished", "terminal_tasks": 100})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    execute(parser.parse_args().output.resolve())


if __name__ == "__main__":
    main()
