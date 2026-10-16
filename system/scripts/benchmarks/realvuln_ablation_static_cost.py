"""Separate actual CodeQL attempts, database reuse and copied scan receipts."""

from scripts.benchmarks.realvuln_ablation_io import csv_write, read
from scripts.benchmarks.realvuln_prepare import save


def export(base, output):
    rows = []
    for root in sorted(base.glob("20261013-*")):
        directories = [root / "static", *root.glob("attempts/*/static")]
        for directory in directories:
            for path in sorted(directory.glob("*/result.json")):
                record = read(path)
                copied = bool(record.get("static_not_rerun"))
                database_reused = bool(record.get("database_reused_from"))
                wall = record.get("wall_seconds")
                extraction = record.get("extract_seconds")
                actual = (
                    0
                    if copied
                    else max(0, wall - extraction)
                    if database_reused and wall is not None and extraction is not None
                    else wall
                )
                rows.append(
                    {
                        "project_id": path.parent.name,
                        "receipt": str(path),
                        "status": record.get("status"),
                        "execution": "copied_successful_receipt"
                        if copied
                        else "actual_query_existing_database"
                        if database_reused
                        else "actual_scan_attempt",
                        "receipt_wall_seconds": wall,
                        "actual_incremental_seconds": actual,
                        "derivation": "copied receipt incurs no new scan"
                        if copied
                        else "receipt wall minus already counted extraction"
                        if database_reused
                        else "original attempt wall",
                        "baseline_reused_from": record.get("baseline_reused_from"),
                        "database_reused_from": record.get("database_reused_from"),
                        "snapshot": record.get("snapshot"),
                        "error": record.get("error"),
                    }
                )
    csv_write(output / "static-resource-ledger.csv", rows)
    summary = {
        "historical_actual_attempts": sum(
            r["execution"] != "copied_successful_receipt" for r in rows
        ),
        "historical_reuse_receipts": sum(
            r["execution"] == "copied_successful_receipt" for r in rows
        ),
        "historical_failed_attempts": sum(r["status"] == "failed" for r in rows),
        "historical_actual_seconds_known": sum(
            r["actual_incremental_seconds"] or 0 for r in rows
        ),
        "unknown_timing_attempts": sum(
            r["actual_incremental_seconds"] is None for r in rows
        ),
        "new_ablation_scan_attempts": 0,
        "meaning": "Actual old scan attempts plus query retries; copied receipts and reused extraction not double-counted; sums are operation time, not GUI latency",
    }
    save(output / "static-resource-summary.json", summary)
    return summary
