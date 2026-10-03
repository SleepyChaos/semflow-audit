"""No-AI semantic baseline: original CodeQL versus manual Flask route extension."""

import json
import statistics
import time
from pathlib import Path
from uuid import uuid4

from app.adapters.codeql.custom import (
    compile_query,
    fixed_dependencies,
    prepare_query,
    run_query,
)
from app.adapters.codeql.flask_spec import RouteShortcut, route_module
from app.adapters.codeql.rule_spec import detector_template
from app.adapters.codeql.scanner import CodeQLScanner
from app.adapters.snapshot import snapshot_digest
from app.core.audit_config import audit_settings
from app.domain.audit import ScanPlan

from scripts.benchmarks.flask_cases import cases, dataset_hash, score

ROOT = Path(__file__).resolve().parents[2]


def main():
    output = ROOT / "artifacts/benchmarks" / f"flask-baseline-{uuid4()}"
    source = output / "source"
    source.mkdir(parents=True)
    rows = cases()
    for row in rows:
        (source / row["file"]).write_text(row["source"])
    report = {
        "scope": "12 constructed Flask routing cases, not CVE or AI quality",
        "dataset_hash": dataset_hash(rows),
        "labels": rows,
        "codeql": CodeQLScanner().version(),
        "dependencies": fixed_dependencies("python"),
        "query_pack": audit_settings.PYTHON_QUERY_PACK,
        "records": [],
    }
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2)
    )
    query, provenance = detector_template("python", "xss")
    module = route_module(
        [
            RouteShortcut(owner=owner, method=method, evidence_id=uuid4())
            for owner in ("Flask", "Blueprint")
            for method in ("get", "post")
        ]
    )
    packs = {}
    for arm in ("original", "manual_model"):
        pack = output / arm
        selected = (
            query
            if arm == "original"
            else query.replace(
                "import python\n", "import python\nimport FlaskRouteModel\n", 1
            )
        )
        prepare_query(
            pack,
            "python",
            selected,
            {} if arm == "original" else {"FlaskRouteModel.qll": module},
            report["dependencies"],
        )
        start = time.perf_counter()
        compile_query(pack, output / f"{arm}-compile.log")
        report.setdefault("compile_seconds", {})[arm] = time.perf_counter() - start
        packs[arm] = pack
    report["template_provenance"] = provenance
    start = time.perf_counter()
    CodeQLScanner().create_database(
        source, output / "database", output / "build.log", ScanPlan("python", "", "")
    )
    report["extract_seconds"] = time.perf_counter() - start
    snapshot = snapshot_digest(source)
    report["snapshot"] = snapshot
    for round_number in range(1, 4):
        for arm in (
            ("original", "manual_model")
            if round_number % 2
            else ("manual_model", "original")
        ):
            start = time.perf_counter()
            findings = run_query(
                output / "database",
                packs[arm],
                output / f"{arm}-{round_number}.sarif",
                output / "queries.log",
                snapshot,
            )
            row = {
                "arm": arm,
                "round": round_number,
                "query_seconds": time.perf_counter() - start,
                "score": score(rows, findings),
            }
            report["records"].append(row)
            (output / "report.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2)
            )
            print(json.dumps(row), flush=True)
    report["median_query_seconds"] = {
        arm: statistics.median(
            r["query_seconds"] for r in report["records"] if r["arm"] == arm
        )
        for arm in packs
    }
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2)
    )
    print("REPORT_PATH=" + str(output / "report.json"), flush=True)


if __name__ == "__main__":
    main()
