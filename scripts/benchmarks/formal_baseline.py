"""Checkpointed actual CodeQL baseline with production suites, no model calls."""

import argparse
import json
import time
from pathlib import Path

from app.adapters.codeql.sarif import parse_sarif
from app.adapters.codeql.scanner import CodeQLScanner
from app.adapters.snapshot import snapshot_digest
from app.domain.audit import ScanPlan

from scripts.benchmarks.formal_freeze import OUTPUT, ROOT, save
from scripts.benchmarks.formal_scoring import score_cases


def run_one(row, config, rounds, output=None):
    directory = (output or OUTPUT) / "static" / row["id"]
    result_path = directory / "result.json"
    if result_path.exists():
        return json.loads(result_path.read_text())
    directory.mkdir(parents=True, exist_ok=True)
    marker = directory / "started.json"
    if marker.exists():
        raise RuntimeError(
            "Interrupted baseline retained; explicitly resume existing DB"
        )
    source = Path(row["source"])
    snapshot = snapshot_digest(source)
    pack = config["packs"][row["language"]]
    plan = ScanPlan(row["language"], pack["pack"], pack["suite"])
    scanner = CodeQLScanner()
    result = {
        "project_id": row["id"],
        "language": row["language"],
        "snapshot": snapshot,
        "suite": plan.suite,
        "pack": plan.query_pack,
        "input_regime": row["input_regime"],
        "rounds": [],
        "scope": "collection calibration; no certified blind accuracy for natural projects",
    }
    save(marker, {"snapshot": snapshot, "suite": plan.suite})
    began = time.perf_counter()
    try:
        start = time.perf_counter()
        scanner.create_database(
            source, directory / "database", directory / "execution.log", plan
        )
        result["extract_seconds"] = time.perf_counter() - start
        for repetition in range(1, rounds + 1):
            start = time.perf_counter()
            sarif = directory / f"round-{repetition}.sarif"
            scanner.analyze(
                directory / "database", sarif, directory / "execution.log", plan
            )
            findings = parse_sarif(sarif, snapshot)
            result["rounds"].append(
                {
                    "round": repetition,
                    "query_seconds": time.perf_counter() - start,
                    "alerts": len(findings),
                    "findings": findings,
                    "cache": "first local database query; OS cache not cleared"
                    if repetition == 1
                    else "same database/query warm reuse",
                }
            )
            if snapshot_digest(source) != snapshot:
                raise RuntimeError("Model input changed during static baseline")
        result["status"] = "succeeded"
        if row["id"] in {"owasp-python", "owasp-python-loader-fixed"}:
            labels = json.loads(
                (
                    ROOT
                    / "benchmark-data/evaluator-only/experiments/20261005-calibration-v1/owasp-labels.json"
                ).read_text()
            )
            result["metrics"] = score_cases(labels, result["rounds"][0]["findings"])
    except Exception as exc:  # noqa: BLE001 - persist failure at benchmark boundary
        result["status"] = "failed"
        result["error_type"] = type(exc).__name__
        result["error"] = str(exc)[:1000]
    result["wall_seconds"] = time.perf_counter() - began
    save(result_path, result)
    print(
        json.dumps(
            {
                k: result.get(k)
                for k in (
                    "project_id",
                    "status",
                    "extract_seconds",
                    "wall_seconds",
                    "error_type",
                )
            }
        ),
        flush=True,
    )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--projects", nargs="*")
    parser.add_argument("--rounds", type=int, default=3)
    args = parser.parse_args()
    config = json.loads((OUTPUT / "config.json").read_text())
    rows = json.loads((OUTPUT / "inputs.json").read_text())["records"]
    if (OUTPUT / "inputs-derived.json").exists():
        rows += json.loads((OUTPUT / "inputs-derived.json").read_text())["records"]
    # Fixed collection order; not sorted by scanning outcomes.
    if args.projects:
        by_id = {row["id"]: row for row in rows}
        rows = [by_id[key] for key in args.projects]
    results = [run_one(row, config, args.rounds) for row in rows]
    save(
        OUTPUT / "static-summary.json",
        {
            "projects": [
                {
                    k: r.get(k)
                    for k in (
                        "project_id",
                        "status",
                        "extract_seconds",
                        "wall_seconds",
                        "rounds",
                    )
                }
                for r in results
            ],
            "model_calls": 0,
        },
    )


if __name__ == "__main__":
    main()
