"""Fail a mechanical pipeline when persisted receipts do not satisfy a gate."""

import argparse
import json
from pathlib import Path

from scripts.benchmarks.full_test_progress import collect


def check(root, phase):
    progress = collect(root)
    if not progress["known_location_repair"]["ready_for_e2e"]:
        raise RuntimeError("Repair receipts still require infrastructure recovery")
    if phase == "e2e":
        if not progress["end_to_end"]["all_have_receipts"]:
            raise RuntimeError("End-to-end receipts incomplete")
        for path in (root / "e2e/system").glob("*/result.json"):
            row = json.loads(path.read_text())
            if row["status"] in {"provider_interrupted", "runner_failed"}:
                raise RuntimeError(
                    f"End-to-end infrastructure recovery required: {path.parent.name}"
                )
    print(json.dumps({"gate": phase, "accepted": True}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--phase", choices=["repair", "e2e"], required=True)
    args = parser.parse_args()
    check(args.output.resolve(), args.phase)


if __name__ == "__main__":
    main()
