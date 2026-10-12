"""CLI-only repeatable static/repair-validator benchmark. No model quality claims."""

import argparse
import hashlib
import json
import platform
import statistics
import sys
import time
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "system/backend"))
sys.path.insert(0, str(Path(__file__).parent))
from corpus import write_corpus, write_repair_cases
from app.adapters.codeql.scanner import CodeQLScanner
from app.adapters.codeql.sarif import parse_sarif
from app.adapters.repair.validator import validate_workspace
from app.adapters.snapshot import snapshot_digest
from app.core.audit_config import audit_settings
from app.domain.audit import ScanPlan


def classification(labels, findings):
    decisions = []
    for label in labels:
        matching = [
            row
            for row in findings
            if any(
                p["file"].endswith(label["file"]) and p["line"] == label["line"]
                for p in row["locations"]
            )
            and any(f"cwe-{label['cwe']}" in tag.lower() for tag in row.get("tags", []))
        ]
        predicted = bool(matching)
        actual = label["vulnerable"]
        decisions.append(
            {
                **label,
                "predicted": predicted,
                "rules": [row["rule"] for row in matching],
                "classification": ("TP" if actual else "FP")
                if predicted
                else ("FN" if actual else "TN"),
            }
        )
    counts = {
        name: sum(row["classification"] == name for row in decisions)
        for name in ["TP", "FP", "FN", "TN"]
    }
    precision = (
        counts["TP"] / (counts["TP"] + counts["FP"])
        if counts["TP"] + counts["FP"]
        else None
    )
    recall = (
        counts["TP"] / (counts["TP"] + counts["FN"])
        if counts["TP"] + counts["FN"]
        else None
    )
    return {
        "counts": counts,
        "precision": precision,
        "recall": recall,
        "f1": 2 * precision * recall / (precision + recall)
        if precision is not None and recall is not None and precision + recall
        else 0,
        "cases": decisions,
        "all_alert_count": len(findings),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rounds", type=int, default=3)
    args = parser.parse_args()
    if not 1 <= args.rounds <= 5:
        parser.error("rounds must be 1..5")
    output = ROOT / "artifacts/benchmarks" / str(uuid4())
    output.mkdir(parents=True)
    report = {
        "schema_version": 1,
        "host": platform.platform(),
        "codeql_version": CodeQLScanner().version(),
        "corpus": "original micro-corpus v1; no training or standard-dataset claim",
        "cache_policy": "fresh database every round; OS and query cache NOT cleared; round 1 is first observed, not guaranteed cold",
        "model": "not configured; no LLM detection/repair-generation accuracy measured",
        "audit": [],
        "repair_validation": [],
    }
    for language in ["python", "javascript"]:
        source = output / language / "source"
        labels = write_corpus(source, language)
        digest = snapshot_digest(source)
        pack = (
            audit_settings.PYTHON_QUERY_PACK
            if language == "python"
            else audit_settings.JAVASCRIPT_QUERY_PACK
        )
        plan = ScanPlan(
            language, pack, f"codeql-suites/{language}-security-extended.qls"
        )
        for index in range(args.rounds):
            directory = output / language / f"round-{index + 1}"
            directory.mkdir(parents=True)
            log, sarif, database = (
                directory / "execution.log",
                directory / "results.sarif",
                directory / "database",
            )
            start = time.perf_counter()
            record = {
                "language": language,
                "round": index + 1,
                "query_pack": pack,
                "snapshot": digest,
            }
            try:
                CodeQLScanner().create_database(source, database, log, plan)
                extraction = time.perf_counter() - start
                scan_start = time.perf_counter()
                CodeQLScanner().analyze(database, sarif, log, plan)
                record.update(
                    status="completed",
                    extract_seconds=extraction,
                    scan_seconds=time.perf_counter() - scan_start,
                    metrics=classification(labels, parse_sarif(sarif, digest)),
                )
            except Exception as exc:
                record.update(status="failed", error=str(exc))
            record["total_seconds"] = time.perf_counter() - start
            report["audit"].append(record)
            print(json.dumps(record, ensure_ascii=False), flush=True)
            (output / "report.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2)
            )
    for case in write_repair_cases(output / "repairs"):
        workspace = Path(case["workspace"])
        before = snapshot_digest(workspace)
        for index in range(args.rounds):
            start = time.perf_counter()
            checks = validate_workspace(workspace, "python", "python_pytest")
            record = {
                **case,
                "round": index + 1,
                "seconds": time.perf_counter() - start,
                "checks": checks,
                "source_unchanged": before == snapshot_digest(workspace),
            }
            report["repair_validation"].append(record)
            print(
                json.dumps(
                    {
                        "repair": case["name"],
                        "round": index + 1,
                        "status": checks["status"],
                        "seconds": record["seconds"],
                    }
                ),
                flush=True,
            )
    report["timings"] = {
        language: {
            "median_seconds": statistics.median(
                row["total_seconds"]
                for row in report["audit"]
                if row["language"] == language and row["status"] == "completed"
            )
        }
        for language in ["python", "javascript"]
        if any(
            row["language"] == language and row["status"] == "completed"
            for row in report["audit"]
        )
    }
    files = {
        str(path.relative_to(output)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in output.rglob("*")
        if path.is_file() and ("source" in path.parts or "repairs" in path.parts)
    }
    report["source_sha256"] = files
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2)
    )
    print("REPORT_PATH=" + str(output / "report.json"))


if __name__ == "__main__":
    main()
