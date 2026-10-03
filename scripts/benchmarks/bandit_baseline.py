"""Compare Bandit on exactly the same Python cases; fixed semantic rule mapping."""

import json
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).parent))
from run_local import classification

report_path = Path(sys.argv[1])
report = json.loads(report_path.read_text())
source = report_path.parent / "python/source"
labels = report["audit"][0]["metrics"]["cases"]
labels = [
    {key: row[key] for key in ["file", "line", "cwe", "vulnerable"]} for row in labels
]
executable = ROOT / "artifacts/competitors/bandit-venv/bin/bandit"
results = {
    "tool": "Bandit 1.9.4",
    "mapping": {"B307": "094", "B605": "078", "B607": "078", "B608": "089"},
    "mapping_note": "map known eval/command/sql checks by semantic purpose; Bandit B307 issue_cwe differs from this corpus CWE-094",
    "rounds": [],
}
for index in range(3):
    output = report_path.parent / f"bandit-round-{index + 1}.json"
    start = time.perf_counter()
    process = subprocess.run(
        [str(executable), "-r", str(source), "-f", "json", "-o", str(output)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    seconds = time.perf_counter() - start
    raw = json.loads(output.read_text())
    record = {"round": index + 1, "seconds": seconds, "exit_code": process.returncode}
    if process.returncode not in [0, 1] or raw.get("errors"):
        record.update(
            status="failed", errors=raw.get("errors"), stderr=process.stderr[-1000:]
        )
    else:
        findings = [
            {
                "rule": row["test_id"],
                "tags": [
                    "external/cwe/cwe-"
                    + results["mapping"].get(row["test_id"], "unknown")
                ],
                "locations": [{"file": row["filename"], "line": row["line_number"]}],
            }
            for row in raw["results"]
        ]
        record.update(status="completed", metrics=classification(labels, findings))
    results["rounds"].append(record)
results["median_seconds"] = statistics.median(
    row["seconds"] for row in results["rounds"]
)
output = report_path.parent / "bandit-report.json"
output.write_text(json.dumps(results, ensure_ascii=False, indent=2))
print(json.dumps(results, ensure_ascii=False))
