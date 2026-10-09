"""Real traditional baselines on identical sample sources with native CWE labels."""

import argparse
import json
import os
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "artifacts/research/owasp48/20261007-evolution"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", required=True)
    args = parser.parse_args()
    material = OUT / "samples" / args.sample
    source = material / "source"
    output = OUT / "comparators" / "bandit" / args.sample
    output.mkdir(parents=True, exist_ok=True)
    if (output / "result.json").exists():
        print("Existing baseline retained")
        return
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(
        ROOT / "artifacts/competitors/bandit-venv/lib/python3.11/site-packages"
    )
    command = [str(ROOT / ".venv/bin/python"), "-m", "bandit"]
    version = subprocess.check_output(
        command + ["--version"], env=environment, text=True
    ).strip()
    rows = []
    for repetition in range(1, 4):
        destination = output / f"round-{repetition}.json"
        started = time.perf_counter()
        result = subprocess.run(
            command + ["-r", str(source), "-f", "json", "-o", str(destination)],
            env=environment,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        seconds = time.perf_counter() - started
        raw = json.loads(destination.read_text()) if destination.exists() else {}
        findings = [
            {
                "id": f"bandit-{index}",
                "rule": row["test_id"],
                "tags": [f"cwe-{row.get('issue_cwe', {}).get('id', 0)}"],
                "locations": [{"file": row["filename"], "line": row["line_number"]}],
            }
            for index, row in enumerate(raw.get("results", []))
        ]
        rows.append(
            {
                "repetition": repetition,
                "seconds": seconds,
                "exit_code": result.returncode,
                "status": "succeeded"
                if result.returncode in (0, 1) and not raw.get("errors")
                else "failed",
                "errors": raw.get("errors"),
                "findings": findings,
            }
        )
    (output / "result.json").write_text(
        json.dumps({"tool": version, "native_CWE": True, "records": rows}, indent=2)
    )
    # No acceptance labels are read here: score only after final implementation freeze.
    print(
        json.dumps(
            {
                "tool": version,
                "sample": args.sample,
                "statuses": [r["status"] for r in rows],
                "seconds": [r["seconds"] for r in rows],
                "alerts": len(rows[0]["findings"]),
            }
        )
    )


if __name__ == "__main__":
    main()
