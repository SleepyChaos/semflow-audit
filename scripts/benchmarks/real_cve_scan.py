"""Explore CodeQL alerts in downloaded pre/post single-file pairs, not full-project recall."""

import json
import shutil
import sys
import time
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from app.adapters.codeql.scanner import CodeQLScanner
from app.adapters.codeql.sarif import parse_sarif
from app.adapters.snapshot import snapshot_digest
from app.core.audit_config import audit_settings
from app.domain.audit import ScanPlan

output = ROOT / "artifacts/benchmarks" / ("real-js-" + str(uuid4()))
output.mkdir(parents=True)
materials = ROOT / "artifacts/research-materials/js-real-cve"
report = {
    "scope": "three real CVE single-file pre/post pairs; incomplete repository context; not complete recall benchmark",
    "oracle": "upstream target line/CWE labels not independently validated; all alerts need root-cause adjudication",
    "codeql": CodeQLScanner().version(),
    "rounds": [],
}
for variant in ["prePatch", "postPatch"]:
    source = output / variant / "source"
    source.mkdir(parents=True)
    labels = []
    for case in sorted(materials.iterdir()):
        label = json.loads((case / "label.json").read_text())
        for file in (case / variant).rglob("*.js"):
            target = source / case.name / file.relative_to(case / variant)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(file, target)
        labels.append(label)
    directory = output / variant
    log = directory / "execution.log"
    digest = snapshot_digest(source)
    plan = ScanPlan(
        "javascript",
        audit_settings.JAVASCRIPT_QUERY_PACK,
        "codeql-suites/javascript-security-extended.qls",
    )
    start = time.perf_counter()
    CodeQLScanner().create_database(source, directory / "database", log, plan)
    extraction = time.perf_counter() - start
    for index in range(3):
        start = time.perf_counter()
        sarif = directory / f"round-{index + 1}.sarif"
        CodeQLScanner().analyze(directory / "database", sarif, log, plan)
        findings = parse_sarif(sarif, digest)
        report["rounds"].append(
            {
                "variant": variant,
                "round": index + 1,
                "extract_seconds_once": extraction,
                "scan_seconds": time.perf_counter() - start,
                "snapshot": digest,
                "labels": labels,
                "findings": findings,
                "alert_count": len(findings),
            }
        )
        (output / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2)
        )
        print(variant, index + 1, len(findings), flush=True)
print("REPORT_PATH=" + str(output / "report.json"))
