"""Actually run installed Bandit against the same OWASP source, exact native CWEs."""

import argparse
import json
import os
import subprocess
import time

from scripts.benchmarks.formal_freeze import OUTPUT, ROOT, save
from scripts.benchmarks.formal_inputs import GOLD, MODEL
from scripts.benchmarks.formal_scoring import score_cases


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--modern-python", action="store_true")
    parser.add_argument("--loader-fixed", action="store_true")
    args = parser.parse_args()
    directory = OUTPUT / (
        "bandit/owasp-python-py314" if args.modern_python else "bandit/owasp-python"
    )
    source = MODEL / "owasp-python"
    if args.loader_fixed:
        directory = OUTPUT / "bandit/owasp-python-loader-fixed-py314"
        source = (
            ROOT
            / "benchmarks/model-inputs/20261005-loader-correction/owasp-python-loader-fixed"
        )
    target = directory / "result.json"
    if target.exists():
        print("EXISTING_BANDIT=" + str(target))
        return
    directory.mkdir(parents=True, exist_ok=True)
    executable = ROOT / "artifacts/competitors/bandit-venv/bin/bandit"
    command = [str(executable)]
    environment = os.environ.copy()
    if args.modern_python:
        command = [str(ROOT / ".venv/bin/python"), "-m", "bandit"]
        environment["PYTHONPATH"] = str(
            ROOT / "artifacts/competitors/bandit-venv/lib/python3.11/site-packages"
        )
    version = subprocess.check_output(
        command + ["--version"], text=True, env=environment
    ).strip()
    labels = json.loads((GOLD / "owasp-labels.json").read_text())
    rows = []
    for repetition in range(1, 4):
        path = directory / f"round-{repetition}.json"
        began = time.perf_counter()
        result = subprocess.run(
            command + ["-r", str(source), "-f", "json", "-o", str(path)],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
            env=environment,
        )
        seconds = time.perf_counter() - began
        document = json.loads(path.read_text()) if path.exists() else {}
        row = {
            "round": repetition,
            "seconds": seconds,
            "exit_code": result.returncode,
            "errors": document.get("errors"),
            "native_CWE_mapping": True,
        }
        if result.returncode in (0, 1) and not document.get("errors"):
            findings = [
                {
                    "id": f"bandit-{i}",
                    "rule": r["test_id"],
                    "tags": [
                        f"external/cwe/cwe-{r.get('issue_cwe', {}).get('id', 0):03}"
                    ],
                    "locations": [{"file": r["filename"], "line": r["line_number"]}],
                }
                for i, r in enumerate(document["results"])
            ]
            row.update(
                status="succeeded",
                alerts=len(findings),
                metrics=score_cases(labels, findings),
            )
        else:
            row.update(status="failed", metrics=None)
        rows.append(row)
    save(
        target,
        {
            "tool": version,
            "records": rows,
            "metric_note": "Exact native CWE labels; taxonomy mismatch is not silently remapped. Not official OWASP scorecard.",
        },
    )
    print(
        json.dumps(
            {
                "tool": version,
                "status": [r["status"] for r in rows],
                "counts": (rows[0].get("metrics") or {}).get("counts"),
            }
        )
    )


if __name__ == "__main__":
    main()
