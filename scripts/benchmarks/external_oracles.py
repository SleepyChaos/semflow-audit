"""Calibrate provided reference patches with published independent oracle cases.

Case strings come from CC BY 4.0 Zenodo 21645415, fixed local material manifest.
The host ONLY parses string literals; project code executes inside the existing
restricted Docker validator. This does not measure LLM patch-generation accuracy.
"""

import ast
import hashlib
import json
import re
import sys
import time
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from app.adapters.repair.validator import validate_workspace
from app.adapters.snapshot import snapshot_digest

SELECTION = [
    ("python", "SQLI", "db.py", "CWE-89"),
    ("python", "XSS", "render.py", "CWE-79"),
    ("python", "AUTHZ", "authz.py", "CWE-862"),
    ("python", "CRLF", "header.py", "CWE-93"),
    ("javascript", "XSS", "render.js", "CWE-79"),
    ("javascript", "PP", "merge.js", "CWE-1321"),
    ("javascript", "OR", "redir.js", "CWE-601"),
    ("javascript", "CRLF", "header.js", "CWE-74"),
]
PY_TEST = """import json, subprocess, sys

def test_independent_oracles(capsys):
    outcomes = {}
    for name in ['security', 'functional']:
        process = subprocess.run([sys.executable, 'run_' + name + '.py'], capture_output=True, text=True, timeout=10)
        outcomes[name] = process.returncode
    with capsys.disabled():
        print('ORACLE_JSON=' + json.dumps(outcomes), flush=True)
    assert outcomes == {'security': 0, 'functional': 0}, outcomes
"""
JS_TEST = """const test = require('node:test');
const assert = require('node:assert/strict');
const cp = require('node:child_process');
test('independent security and functional oracles', () => {
  const outcomes = {};
  for (const name of ['security', 'functional']) {
    const result = cp.spawnSync(process.execPath, ['run_' + name + '.js'], {encoding:'utf8',timeout:10000});
    outcomes[name] = result.error ? 'execution_error' : result.status;
  }
  console.log('ORACLE_JSON=' + JSON.stringify(outcomes));
  assert.deepEqual(outcomes, {security:0, functional:0});
});
"""


def main():
    materials = (
        ROOT
        / "artifacts/research-materials/execution-patching-examples/harness/oracle/examples"
    )
    constants, hashes = {}, {}
    for language, filename in [
        ("python", "py_benchmark.py"),
        ("javascript", "js_benchmark.py"),
    ]:
        path = materials / filename
        hashes[language] = hashlib.sha256(path.read_bytes()).hexdigest()
        constants[language] = {}
        for node in ast.parse(path.read_text()).body:
            if (
                isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
            ):
                try:
                    value = ast.literal_eval(node.value)
                except (ValueError, TypeError):
                    continue
                if isinstance(value, str):
                    constants[language][node.targets[0].id] = value
    directory = ROOT / "artifacts/benchmarks" / ("external-oracles-" + str(uuid4()))
    directory.mkdir(parents=True)
    report = {
        "source": "https://zenodo.org/records/21645415",
        "license": "CC BY 4.0",
        "material_sha256": hashes,
        "scope": "8 published miniature cases; supplied reference fixes, NOT platform-generated patches or full CVE repositories",
        "rounds": [],
    }
    for language, symbol, target, cwe in SELECTION:
        values = constants[language]
        extension = "py" if language == "python" else "js"
        for variant, suffix in [("vulnerable", "VULN"), ("reference_fix", "FIX")]:
            workspace = directory / (language + "-" + symbol.lower()) / variant
            workspace.mkdir(parents=True)
            (workspace / target).write_text(values["_" + symbol + "_" + suffix])
            (workspace / ("run_security." + extension)).write_text(
                values["_" + symbol + "_SEC"]
            )
            (workspace / ("run_functional." + extension)).write_text(
                values["_" + symbol + "_FUN"]
            )
            (
                workspace
                / ("test_oracles.py" if language == "python" else "oracles.test.js")
            ).write_text(PY_TEST if language == "python" else JS_TEST)
            before = snapshot_digest(workspace)
            for index in range(3):
                start = time.perf_counter()
                checks = validate_workspace(
                    workspace,
                    language,
                    "python_pytest" if language == "python" else "javascript_test",
                )
                found = re.search(r"ORACLE_JSON=(\{[^\n]+\})", checks.get("output", ""))
                outcomes = json.loads(found.group(1)) if found else None
                row = {
                    "language": language,
                    "case": symbol,
                    "cwe": cwe,
                    "variant": variant,
                    "round": index + 1,
                    "seconds": time.perf_counter() - start,
                    "outcomes": outcomes,
                    "validation": checks,
                    "source_unchanged": snapshot_digest(workspace) == before,
                    "snapshot": before,
                }
                row["oracle_calibrated"] = (
                    outcomes == {"security": 1, "functional": 0}
                    if variant == "vulnerable"
                    else outcomes == {"security": 0, "functional": 0}
                )
                report["rounds"].append(row)
                (directory / "report.json").write_text(
                    json.dumps(report, ensure_ascii=False, indent=2)
                )
                print(
                    json.dumps(
                        {
                            k: row[k]
                            for k in [
                                "language",
                                "case",
                                "variant",
                                "round",
                                "seconds",
                                "outcomes",
                                "oracle_calibrated",
                            ]
                        }
                    ),
                    flush=True,
                )
    print("REPORT_PATH=" + str(directory / "report.json"))


if __name__ == "__main__":
    main()
