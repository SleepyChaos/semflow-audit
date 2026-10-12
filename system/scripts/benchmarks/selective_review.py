"""Matched follow-up on frozen review input; preserve every failed/unknown verdict."""

import argparse
import json
import logging
import time
from pathlib import Path

from app.jobs.stages import execute_stage

from scripts.benchmarks.flask_live import capture, stage

ROOT = Path(__file__).resolve().parents[3]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("reference", type=Path)
    args = parser.parse_args()
    logging.basicConfig(level=logging.CRITICAL)
    old = json.loads(args.reference.read_text())
    original = old["review"][0]["stage"]
    output = args.reference.parent / "selective-review.json"
    report = {
        "scope": "same 7 actual CodeQL alerts from 12 constructed Flask cases; follow-up, not independent CVEs",
        "reference": str(args.reference),
        "dataset_hash": old["dataset_hash"],
        "arms": {
            "dedup_v2": "only exact evidence reuse",
            "selective_v3": "dedup plus missing-premise acquisition prompt",
        },
        "records": [],
    }
    for repetition in range(1, 4):
        for arm, version in (("dedup_v2", "2"), ("selective_v3", "3")):
            policy = {
                k: v
                for k, v in original["model_config_snapshot"].items()
                if k != "prompt_snapshot"
            }
            identifier = stage(
                original["audit_id"], "review", original["inputs"], policy, version
            )
            start = time.perf_counter()
            execute_stage.run(identifier)
            row = {
                "arm": arm,
                "round": repetition,
                "seconds": time.perf_counter() - start,
                **capture(identifier),
            }
            # Match only the reference evaluator's known source locations.
            locations = {
                (c["location"]["file"], c["location"]["line"]): s["vulnerable"]
                for c, s in zip(
                    old["review"][0]["candidates"],
                    old["review"][0]["assessment_scores"],
                    strict=True,
                )
            }
            row["scores"] = [
                {
                    "assessment": c["model_assessment"],
                    "vulnerable": locations.get(
                        (c["location"]["file"], c["location"]["line"])
                    ),
                }
                for c in row["candidates"]
            ]
            report["records"].append(row)
            output.write_text(json.dumps(report, ensure_ascii=False, indent=2))
            print(
                arm,
                repetition,
                row["stage"]["status"],
                row["stage"]["usage"],
                flush=True,
            )
    print("REPORT_PATH=" + str(output), flush=True)


if __name__ == "__main__":
    main()
