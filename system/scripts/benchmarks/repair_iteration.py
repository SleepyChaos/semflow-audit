"""Run a frozen, explicitly selected repair development batch, preserving every round."""

import argparse
import json
import time
from pathlib import Path

from scripts.benchmarks.mechanical_pipeline import exclusive, save


def run(root):
    from scripts.benchmarks.realvuln_run import verify_implementation
    from scripts.benchmarks.vul4py_repair import run as repair

    with exclusive(root / "iteration.lock"):
        protocol = json.loads((root / "iteration-protocol.json").read_text())
        cases = protocol["cases"]
        manifest = json.loads((root / "manifest.json").read_text())
        known = {r["vuln_id"] for r in manifest["cases"]}
        if (
            not 1 <= len(cases) <= 8
            or len(set(cases)) != len(cases)
            or not set(cases) <= known
        ):
            raise RuntimeError("Expected a unique, explicit small batch (1..8 cases)")
        config = json.loads((root / "repair-config.json").read_text())
        if config["prompt_version"] != protocol["prompt_version"]:
            raise RuntimeError("Frozen prompt identity mismatch")
        for identity in cases:
            verify_implementation(root)
            start = time.monotonic()
            reused = (root / "runs" / identity / "result.json").exists()
            repair(identity, root, config["policy"], config["image_id"])
            timing = root / "case-timing" / f"{identity}.json"
            if not timing.exists():
                save(
                    timing,
                    {
                        "elapsed_this_invocation_seconds": time.monotonic() - start,
                        "receipt_reused": reused,
                    },
                )
            rows = [
                json.loads((root / "runs" / case / "result.json").read_text())
                for case in cases
                if (root / "runs" / case / "result.json").exists()
            ]
            save(
                root / "iteration-summary.json",
                {
                    "planned": len(cases),
                    "completed": len(rows),
                    "evaluated": sum(r["status"] == "evaluated" for r in rows),
                    "joint_pass": sum(r.get("joint_pass") is True for r in rows),
                    "cases": rows,
                    "full_test_resumed": False,
                },
            )
            generation = root / "runs" / identity / "generation.json"
            if generation.exists():
                stage = json.loads(generation.read_text())["stage"]
                calls = stage.get("model_calls", [])
                if calls and calls[-1].get("error_code") in {
                    "provider_error",
                    "rate_limited",
                    "timeout",
                }:
                    raise RuntimeError(
                        "Provider interrupted; recorded attempt retained, no automatic replay"
                    )
        verify_implementation(root)
        save(
            root / "iteration-finished.json",
            {"status": "completed", "tasks": len(cases)},
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    run(args.output.resolve())


if __name__ == "__main__":
    main()
