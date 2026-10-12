"""Complete-snapshot SAST/timing pilot; pending labels never become precision scores."""

import argparse
import json
import platform
import time
from pathlib import Path
from uuid import uuid4

from app.adapters.codeql.sarif import parse_sarif
from app.adapters.codeql.scanner import CodeQLScanner
from app.adapters.snapshot import snapshot_digest
from app.core.audit_config import audit_settings
from app.domain.audit import AuditError, ScanPlan

ROOT = Path(__file__).resolve().parents[3]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--per-language", type=int, default=2)
    args = parser.parse_args()
    materials = json.loads(args.manifest.read_text())
    selected = []
    for language in ("javascript", "python"):
        # Selected from the frozen list, not from tool success or vulnerability scores.
        selected.extend(
            [r for r in materials["records"] if r["language"] == language][
                : args.per_language
            ]
        )
    output = ROOT / "artifacts/benchmarks" / f"real-pair-pilot-{uuid4()}"
    output.mkdir()
    scanner = CodeQLScanner()
    report = {
        "scope": "first 2 frozen full repository pairs per language; extraction/query/timing and target-location exploration, not adjudicated audit accuracy",
        "selection": [r["case_id"] for r in selected],
        "material_manifest": str(args.manifest),
        "machine": platform.platform(),
        "codeql": scanner.version(),
        "threads": audit_settings.CODEQL_THREADS,
        "ram": audit_settings.CODEQL_RAM,
        "timing": "first query includes compilation; repeated same DB/query may reuse normal CodeQL cache; OS caches not cleared; no dynamic generated query caching",
        "records": [],
    }
    path = output / "report.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print("OUTPUT=" + str(output), flush=True)
    for row in selected:
        for variant in ("pre", "post"):
            result = {
                "case_id": row["case_id"],
                "advisory": row["cve"],
                "repository": row["repository"],
                "language": row["language"],
                "variant": variant,
                "label_status": row["label_status"],
                "oracle_status": row["oracle_status"],
                "rounds": [],
            }
            directory = output / row["case_id"] / variant
            directory.mkdir(parents=True)
            start = time.perf_counter()
            try:
                if row.get("collection_status") != "downloaded":
                    raise AuditError(
                        "Frozen selected material unavailable; not replaced"
                    )
                source = args.manifest.parent / row["case_id"] / variant
                digest = snapshot_digest(source)
                result["snapshot"] = digest
                result["commit"] = row[variant + "_commit"]
                pack = (
                    audit_settings.PYTHON_QUERY_PACK
                    if row["language"] == "python"
                    else audit_settings.JAVASCRIPT_QUERY_PACK
                )
                prefix = "python" if row["language"] == "python" else "javascript"
                plan = ScanPlan(
                    row["language"],
                    pack,
                    f"codeql-suites/{prefix}-security-extended.qls",
                )
                result["query_pack"] = pack
                scanner.create_database(
                    source, directory / "database", directory / "execution.log", plan
                )
                result["extract_seconds"] = time.perf_counter() - start
                for repetition in range(1, 4):
                    began = time.perf_counter()
                    sarif = directory / f"round-{repetition}.sarif"
                    scanner.analyze(
                        directory / "database", sarif, directory / "execution.log", plan
                    )
                    findings = parse_sarif(sarif, digest)
                    scored = {
                        "round": repetition,
                        "query_seconds": time.perf_counter() - began,
                        "alert_count": len(findings),
                        "findings": findings,
                    }
                    if variant == "pre" and row.get("labels"):
                        scored["upstream_exact_location_hits"] = [
                            {
                                "label": w,
                                "rules": sorted(
                                    {
                                        f["rule"]
                                        for f in findings
                                        if any(
                                            p["file"] == w["location"]["file"]
                                            and p["line"] == w["location"]["line"]
                                            for p in f["locations"]
                                        )
                                    }
                                ),
                            }
                            for w in row["labels"]
                        ]
                    result["rounds"].append(scored)
                    if snapshot_digest(source) != digest:
                        raise AuditError("Material changed during evaluation")
                result["status"] = "completed"
            except (AuditError, OSError, ValueError) as exc:
                result["status"] = "failed"
                result["error"] = {"type": type(exc).__name__, "message": str(exc)}
            result["total_seconds"] = time.perf_counter() - start
            report["records"].append(result)
            path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
            print(
                row["cve"],
                variant,
                result["status"],
                result.get("extract_seconds"),
                flush=True,
            )
    print("REPORT_PATH=" + str(path), flush=True)


if __name__ == "__main__":
    main()
