"""Freeze anonymous full-project inputs for the independent Vul4Py chain."""

import argparse
import json
import shutil
from pathlib import Path

from app.adapters.ai.policy import policy_snapshot
from app.adapters.codeql.scanner import CodeQLScanner
from app.adapters.snapshot import snapshot_digest
from app.core.audit_config import audit_settings
from app.domain.audit import AuditError
from scripts.benchmarks.realvuln_run import verify_implementation
from scripts.benchmarks.vul4py_prepare import save


def prepare(root, scheduling_profile="full"):
    verify_implementation(root)
    output = root / "e2e"
    output.mkdir(exist_ok=True)
    records_path = output / "inputs.json"
    if records_path.exists():
        return json.loads(records_path.read_text())["records"]
    cases = json.loads((root / "manifest.json").read_text())["cases"]
    records, mapping = [], []
    for number, case in enumerate(cases, 1):
        identity = f"case-{number:03d}"
        source = output / "sources" / identity
        row = {
            "id": identity,
            "source": str(source),
            "language": "python",
            "input_regime": "full original source; no vulnerability description, locations, reference patch or hidden tests",
            "status": "prepared",
        }
        try:
            pristine = root / "workspaces" / case["vuln_id"] / "vulnerable"
            digest = snapshot_digest(pristine)
            if not source.exists():
                shutil.copytree(pristine, source)
            if snapshot_digest(source) != digest:
                raise RuntimeError("Anonymous copy differs from immutable input")
            row.update(
                snapshot=digest, files=sum(p.is_file() for p in source.rglob("*"))
            )
        except (OSError, RuntimeError, AuditError) as error:
            row.update(status="input_failed", error=str(error))
        records.append(row)
        mapping.append({"project_id": identity, "vuln_id": case["vuln_id"]})
    repair = json.loads((root / "repair-config.json").read_text())["policy"]
    config = {
        "codeql_cli": CodeQLScanner().version(),
        "packs": {
            "python": {
                "pack": audit_settings.PYTHON_QUERY_PACK,
                "suite": "codeql-suites/python-code-scanning.qls",
            }
        },
        "model_policies": {kind: policy_snapshot(kind) for kind in ("scout", "review")},
        "repair_policy": repair,
        "versions": {"scout": "7", "review": "12", "repair": "3"},
        "scout_request": {"scheduling_profile": scheduling_profile},
        "selection": "all 100 original versions in frozen manifest order; sequential isolated projects",
        "repair_selection": "every AI-supported, automatically confirmed Review12 candidate, UUID order; independent patch per candidate; no gold filtering",
        "repair_input": "candidate description and actual evidence only; allowed paths inferred by production Repair2",
        "confirmation": "validated AI evidence classification; no human decisions inserted",
        "evaluation": "hidden dual oracle only after patch; no oracle feedback to model",
        "primary_success": "at least one independent patch per project passes both hidden security and functional tests on a calibrated case",
        "scope": "production core workflows; GUI, upload, human patch acceptance and deployment not exercised",
    }
    save(output / "config.json", config)
    save(output / "evaluator-only-mapping.json", {"records": mapping})
    save(records_path, {"records": records, "total_frozen": 100})
    return records


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--scheduling-profile", choices=["full", "runtime_first"], default="full"
    )
    args = parser.parse_args()
    records = prepare(args.output.resolve(), args.scheduling_profile)
    print(
        "Frozen end-to-end inputs:",
        len(records),
        "prepared:",
        sum(r["status"] == "prepared" for r in records),
    )


if __name__ == "__main__":
    main()
