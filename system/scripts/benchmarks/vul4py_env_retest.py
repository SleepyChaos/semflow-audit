"""Versioned environment-only retries; never overwrite original repair scores."""

import argparse
import json
from pathlib import Path

from scripts.benchmarks.cqllm_materials import sha
from scripts.benchmarks.mechanical_pipeline import exclusive, save
from scripts.benchmarks.vul4py_oracle import calibrate


def select_cases(origin):
    selected = []
    for case in json.loads((origin / "manifest.json").read_text())["cases"]:
        identity = case["vuln_id"]
        receipt = origin / "calibration" / identity / "result.json"
        if json.loads(receipt.read_text())["accepted"]:
            continue
        logs = origin / "evaluator" / identity / "logs"
        text = "\n".join(
            p.read_text(errors="replace")[-12000:]
            for p in logs.glob("*.log")
            if p.name.startswith(("functional_", "exploit_"))
        )
        if (
            "ModuleNotFoundError: No module named" in text
            or "unrecognized arguments:" in text
        ):
            selected.append(
                {"vuln_id": identity, "parent_receipt_sha256": sha(receipt)}
            )
    return selected


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--origin", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--projects", nargs="+")
    parser.add_argument("--wait-for-lock", action="store_true")
    parser.add_argument(
        "--profile",
        choices=["project-declared", "project-compatible"],
        default="project-declared",
    )
    args = parser.parse_args()
    origin, output = args.origin.resolve(), args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    with exclusive(output / "oracle.lock", blocking=args.wait_for_lock):
        cases = select_cases(origin)
        protocol = {
            "origin": str(origin),
            "cases": cases,
            "profile": args.profile,
            "new_model_calls": 0,
        }
        if args.profile == "project-compatible":
            protocol["environment_profile_sha256"] = sha(
                output / "environment-profile.json"
            )
        path = output / "retest-protocol.json"
        if path.exists() and json.loads(path.read_text()) != protocol:
            raise RuntimeError("Environment retest inputs changed")
        save(path, protocol)
        for name in ("workspaces", "upstream", "evaluator-tools", "acquisition"):
            alias = output / name
            if not alias.exists():
                alias.symlink_to(origin / name, target_is_directory=True)
        ids = [r["vuln_id"] for r in cases]
        if args.projects:
            if not set(args.projects) <= set(ids):
                raise RuntimeError(
                    "Requested task lacks eligible infrastructure failure"
                )
            ids = args.projects
        image = json.loads((origin / "oracle-config.json").read_text())["image_id"]
        for identity in ids:
            calibrate(identity, output, image, args.profile)
            receipts = [
                json.loads(p.read_text())
                for p in (output / "calibration").glob("*/result.json")
            ]
            save(
                output / "summary.json",
                {
                    "selected": len(cases),
                    "attempted": len(receipts),
                    "accepted": sum(r["accepted"] for r in receipts),
                    "new_model_calls": 0,
                    "original_results_preserved": True,
                },
            )


if __name__ == "__main__":
    main()
