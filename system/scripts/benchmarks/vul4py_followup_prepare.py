"""Freeze a repaired implementation with fresh model stages and baseline oracles."""

import argparse
import json
import shutil
from pathlib import Path

from scripts.benchmarks.benchmark_integrity import implementation_hashes
from scripts.benchmarks.cqllm_materials import sha
from scripts.benchmarks.mechanical_pipeline import save

REPO = Path(__file__).resolve().parents[3]


def prepare(origin, output):
    receipt = output / "followup-inputs.json"
    if receipt.exists():
        record = json.loads(receipt.read_text())
        if record["origin"] != str(origin) or implementation_hashes(
            output / "implementation"
        ) != json.loads((output / "implementation-hashes.json").read_text()):
            raise RuntimeError("Frozen followup identity changed")
        for name, digest in record["parent_receipts"].items():
            if sha(origin / name) != digest:
                raise RuntimeError("Parent oracle receipt changed")
        return record
    if output.exists() and any(output.iterdir()):
        raise RuntimeError("Partial followup preparation requires explicit recovery")
    output.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((origin / "manifest.json").read_text())
    identities = [r["vuln_id"] for r in manifest["cases"]]
    if len(identities) != 100 or len(set(identities)) != 100:
        raise RuntimeError("Expected full 100-task source manifest")
    parent_receipts = {}
    for name in ("manifest.json", "oracle-config.json"):
        shutil.copyfile(origin / name, output / name)
        parent_receipts[name] = sha(origin / name)
    accepted = 0
    for identity in identities:
        name = f"calibration/{identity}/result.json"
        path = origin / name
        row = json.loads(path.read_text())
        if row["vuln_id"] != identity:
            raise RuntimeError("Parent calibration identity mismatch")
        (output / name).parent.mkdir(parents=True)
        shutil.copyfile(path, output / name)
        parent_receipts[name] = sha(path)
        if row["accepted"]:
            accepted += 1
            case = output / "evaluator" / identity
            case.mkdir(parents=True)
            source = origin / "workspaces" / identity
            shutil.copyfile(source / "meta.json", case / "meta.json")
            shutil.copytree(source / "fixed", case / "fixed", symlinks=True)
    for name in ("workspaces", "upstream", "acquisition", "evaluator-tools"):
        (output / name).symlink_to(origin / name, target_is_directory=True)
    frozen = output / "implementation"
    for name in ("system/backend/app", "system/scripts"):
        shutil.copytree(
            REPO / name,
            frozen / name,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
    # Local execution alias only: archives must never follow or include this link.
    (frozen / ".env").symlink_to(REPO / ".env")
    save(output / "implementation-hashes.json", implementation_hashes(frozen))
    record = {
        "origin": str(origin),
        "total_frozen": 100,
        "calibrated": accepted,
        "parent_receipts": parent_receipts,
        "new_model_stages": True,
        "old_results_overwritten": False,
        "oracle_regime": "reuse immutable original calibration; no mixing environment-only variants; noncalibrated tasks remain not_evaluated",
        "implementation": "current repaired app and benchmark runners frozen before execution",
        "local_secret_alias_excluded_from_archives": True,
    }
    save(receipt, record)
    return record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--origin", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.origin.resolve(), args.output.resolve())), flush=True)


if __name__ == "__main__":
    main()
