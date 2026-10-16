"""Consume individually calibrated cases, preserving all 100 terminal outcomes."""

import argparse
import json
import time
from pathlib import Path

from app.adapters.ai.policy import policy_snapshot
from scripts.benchmarks.vul4py_prepare import save
from scripts.benchmarks.vul4py_repair import run


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    ids = [
        r["vuln_id"]
        for r in json.loads((output / "manifest.json").read_text())["cases"]
    ]
    config = json.loads((output / "repair-config.json").read_text())
    expected = policy_snapshot("repair")
    expected.update(
        max_calls=0,
        max_tokens=0,
        max_seconds=0,
        execution_mode="progress_with_local_repair_attempt_and_tool_limits",
    )
    if expected != config["policy"]:
        raise RuntimeError("Frozen repair policy changed")
    while True:
        progressed = False
        for identity in ids:
            result_path = output / "runs" / identity / "result.json"
            calibration = output / "calibration" / identity / "result.json"
            if result_path.exists() or not calibration.exists():
                continue
            result = run(identity, output, config["policy"], config["image_id"])
            progressed = True
            if result.get("stage_id"):
                generation = json.loads(
                    (output / "runs" / identity / "generation.json").read_text()
                )
                records = generation["stage"].get("model_calls", [])
                if records and records[-1].get("error_code") in {
                    "rate_limited",
                    "provider_error",
                    "timeout",
                }:
                    save(
                        output / "pipeline-status.json",
                        {
                            "status": "provider_interrupted",
                            "case": identity,
                            "stage_id": result["stage_id"],
                            "reason": "No further paid requests until connection/provider recovery",
                        },
                    )
                    return
        completed = [
            json.loads((output / "runs" / i / "result.json").read_text())
            for i in ids
            if (output / "runs" / i / "result.json").exists()
        ]
        save(
            output / "pipeline-status.json",
            {
                "status": "running" if len(completed) < 100 else "finished",
                "frozen_tasks": 100,
                "terminal_tasks": len(completed),
                "joint_pass": sum(r["joint_pass"] for r in completed),
            },
        )
        if len(completed) == 100:
            save(
                output / "repair-summary.json",
                {
                    "cases": completed,
                    "attempted": 100,
                    "total_frozen": 100,
                    "joint_pass": sum(r["joint_pass"] for r in completed),
                    "human_correct": None,
                    "all_tasks_have_status": True,
                },
            )
            return
        if not progressed:
            time.sleep(20)


if __name__ == "__main__":
    main()
