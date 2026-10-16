"""Reconcile persisted full-test receipts without DB, Docker or model calls."""

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from scripts.benchmarks.benchmark_integrity import implementation_hashes


def read(path):
    return json.loads(path.read_text())


def receipts(directory, identities):
    rows, missing, errors = {}, [], []
    for identity in identities:
        path = directory / identity / "result.json"
        if not path.exists():
            missing.append(identity)
            continue
        try:
            row = read(path)
            if not isinstance(row, dict) or not isinstance(row.get("status"), str):
                raise TypeError("receipt needs a status")
            declared = row.get("vuln_id", row.get("project_id"))
            if declared != identity:
                raise ValueError("receipt identity differs from manifest")
            rows[identity] = row
        except (TypeError, ValueError, OSError) as error:
            errors.append({"identity": identity, "error": str(error)})
    extra = sorted(
        p.parent.name
        for p in directory.glob("*/result.json")
        if p.parent.name not in identities
    )
    return {
        "expected": len(identities),
        "records": len(rows),
        "all_have_receipts": not (missing or errors or extra),
        "statuses": dict(Counter(r["status"] for r in rows.values())),
        "missing": missing,
        "invalid": errors,
        "unexpected": extra,
    }, rows


def collect(root):
    cases = read(root / "manifest.json")["cases"]
    ids = [r["vuln_id"] for r in cases]
    if len(ids) != 100 or len(set(ids)) != 100:
        raise ValueError("Expected exactly 100 unique frozen Vul4Py identities")
    calibration, calibrated = receipts(root / "calibration", ids)
    calibration["accepted"] = sum(
        r.get("accepted") is True for r in calibrated.values()
    )
    repair, repaired = receipts(root / "runs", ids)
    repair.update(
        actual_stages=sum(bool(r.get("stage_id")) for r in repaired.values()),
        patches_evaluated=sum(r["status"] == "evaluated" for r in repaired.values()),
        joint_pass=sum(r.get("joint_pass") is True for r in repaired.values()),
        failure_reasons=dict(
            Counter(
                r.get("reason", "unspecified")
                for r in repaired.values()
                if r["status"] == "repair_failed"
            )
        ),
    )
    interruptions = []
    for identity in ids:
        path = root / "runs" / identity / "generation.json"
        if not path.exists():
            continue
        stage = read(path)["stage"]
        calls = stage.get("model_calls", [])
        if (
            stage.get("status") == "failed"
            and calls
            and calls[-1].get("error_code")
            in {"provider_error", "rate_limited", "timeout"}
        ):
            interruptions.append(identity)
    frozen = implementation_hashes(root / "implementation")
    expected = read(root / "implementation-hashes.json")
    integrity = {
        "matches": frozen == expected,
        "files": len(expected),
        "added": sorted(frozen.keys() - expected.keys()),
        "missing": sorted(expected.keys() - frozen.keys()),
        "changed": sorted(
            k for k in frozen.keys() & expected.keys() if frozen[k] != expected[k]
        ),
    }
    blocked = [
        i
        for i, r in repaired.items()
        if r.get("reason") == "Frozen implementation changed"
    ]
    repair["recovery_required"] = {
        "provider_interrupted": interruptions,
        "integrity_guard": blocked,
    }
    # A count of terminal JSONs alone is not an acceptance gate for the next stage.
    repair["ready_for_e2e"] = (
        repair["all_have_receipts"]
        and calibration["all_have_receipts"]
        and integrity["matches"]
        and not (interruptions or blocked)
    )
    inputs = read(root / "e2e/inputs.json")["records"]
    projects = [r["id"] for r in inputs]
    if len(projects) != 100 or len(set(projects)) != 100:
        raise ValueError("Expected exactly 100 unique end-to-end input identities")
    e2e, _ = receipts(root / "e2e/system", projects)
    e2e["input_statuses"] = dict(Counter(r["status"] for r in inputs))
    cqllm_root = root.parents[1] / "cqllm/20261015-full-v1"
    cqllm_manifest = cqllm_root / "manifest.json"
    cqllm_summary = cqllm_root / "summary.json"
    cqllm_execution = read(cqllm_summary) if cqllm_summary.exists() else {}
    return {
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "output": str(root),
        "calibration": calibration,
        "known_location_repair": repair,
        "implementation_integrity": integrity,
        "end_to_end": e2e,
        "cqllm": {
            "output": str(cqllm_root),
            "status": "manifest_present_execution_needs_verification"
            if cqllm_manifest.exists()
            else "not_started",
            "runner_ready": Path(__file__).with_name("cqllm_run.py").exists(),
            "execution": cqllm_execution,
        },
        "next_action": "recover_infrastructure_receipts_and_calibration"
        if not repair["ready_for_e2e"]
        else "run_full_source_e2e",
        "no_model_calls_made_by_this_check": True,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--save", type=Path)
    args = parser.parse_args()
    result = collect(args.output.resolve())
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.save:
        args.save.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.save.with_suffix(".tmp")
        temporary.write_text(text)
        temporary.replace(args.save)
    print(text)


if __name__ == "__main__":
    main()
