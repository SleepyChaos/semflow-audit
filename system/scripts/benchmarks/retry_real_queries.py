"""Explicit resource-profile follow-up on failed full-repo queries; retain baseline."""

import argparse
import json
import time
from pathlib import Path

from app.adapters.codeql.sarif import parse_sarif
from app.adapters.codeql.scanner import CodeQLScanner
from app.adapters.snapshot import snapshot_digest
from app.core.audit_config import audit_settings
from app.domain.audit import AuditError, ScanPlan


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("reference", type=Path)
    parser.add_argument("--ram", type=int, default=4096)
    parser.add_argument("--threads", type=int, default=1)
    args = parser.parse_args()
    baseline = json.loads(args.reference.read_text())
    materials = Path(baseline["material_manifest"])
    audit_settings.CODEQL_RAM = args.ram
    audit_settings.CODEQL_THREADS = args.threads
    output = args.reference.parent / f"resource-{args.ram}-{args.threads}"
    output.mkdir()
    report = {
        "scope": "resource profile follow-up; same fixed source and queries, baseline failures retained",
        "reference": str(args.reference),
        "ram": args.ram,
        "threads": args.threads,
        "records": [],
    }
    for old in baseline["records"]:
        if old["status"] != "failed" or "extract_seconds" not in old:
            continue
        directory = args.reference.parent / old["case_id"] / old["variant"]
        source = materials.parent / old["case_id"] / old["variant"]
        row = {
            k: v
            for k, v in old.items()
            if k not in ("rounds", "error", "status", "total_seconds")
        }
        row["rounds"] = []
        try:
            if snapshot_digest(source) != old["snapshot"]:
                raise AuditError("Frozen source changed")
            prefix = "python" if old["language"] == "python" else "javascript"
            plan = ScanPlan(
                old["language"],
                old["query_pack"],
                f"codeql-suites/{prefix}-security-extended.qls",
            )
            for repetition in range(1, 4):
                start = time.perf_counter()
                sarif = output / f"{old['case_id']}-{old['variant']}-{repetition}.sarif"
                CodeQLScanner().analyze(
                    directory / "database", sarif, output / "execution.log", plan
                )
                findings = parse_sarif(sarif, old["snapshot"])
                row["rounds"].append(
                    {
                        "round": repetition,
                        "query_seconds": time.perf_counter() - start,
                        "alert_count": len(findings),
                        "findings": findings,
                    }
                )
            row["status"] = "completed"
        except (AuditError, OSError, ValueError) as exc:
            row["status"] = "failed"
            row["error"] = {"type": type(exc).__name__, "message": str(exc)}
        report["records"].append(row)
        (output / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2)
        )
        print(old["advisory"], old["variant"], row["status"], flush=True)
    print("REPORT_PATH=" + str(output / "report.json"), flush=True)


if __name__ == "__main__":
    main()
