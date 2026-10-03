"""Evaluate a supplied RAG seed query on independent examples, not LLM synthesis quality."""

import json
import sys
import time
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from app.adapters.codeql.custom import (
    compile_query,
    fixed_dependencies,
    prepare_query,
    run_query,
)
from app.adapters.codeql.sarif import parse_sarif
from app.adapters.codeql.scanner import CodeQLScanner
from app.adapters.snapshot import snapshot_digest
from app.core.audit_config import audit_settings
from app.domain.audit import ScanPlan

CASES = [
    (
        "direct",
        True,
        'def handler():\n    return str(eval(request.args["value"])) # target\n',
    ),
    (
        "propagated",
        True,
        'def handler():\n    value = request.args["value"]\n    return str(eval(value)) # target\n',
    ),
    (
        "wrapper",
        True,
        'def evaluate(value):\n    return eval(value) # target\n@app.get("/wrapper")\ndef handler():\n    return str(evaluate(request.args["value"]))\n',
    ),
    (
        "aliased",
        True,
        'def handler():\n    evaluate = eval\n    return str(evaluate(request.args["value"])) # target\n',
    ),
    ("constant", False, 'def handler():\n    return str(eval("1+2")) # target\n'),
    (
        "sanitized_integer",
        False,
        'def handler():\n    value = str(int(request.args["value"]))\n    return str(eval(value)) # target\n',
    ),
    (
        "shadowed_function",
        False,
        'def eval(value):\n    return value\n@app.get("/shadowed")\ndef handler():\n    return eval(request.args["value"]) # target\n',
    ),
    (
        "numeric_conversion",
        False,
        'def handler():\n    return str(int(request.args["value"])) # target\n',
    ),
]
HEADER = 'from flask import Flask, request\napp = Flask(__name__)\n@app.get("/")\n'


def evaluate(labels, findings, rule=None):
    cases = []
    for label in labels:
        hits = [
            row
            for row in findings
            if (not rule or row["rule"] == rule)
            and any(
                p["file"].endswith(label["file"]) and p["line"] == label["line"]
                for p in row["locations"]
            )
        ]
        prediction = bool(hits)
        actual = label["vulnerable"]
        cases.append(
            {
                **label,
                "predicted": prediction,
                "classification": ("TP" if actual else "FP")
                if prediction
                else ("FN" if actual else "TN"),
                "rules": [row["rule"] for row in hits],
            }
        )
    counts = {
        key: sum(c["classification"] == key for c in cases)
        for key in ["TP", "FP", "FN", "TN"]
    }
    return {
        "cases": cases,
        "counts": counts,
        "precision": counts["TP"] / (counts["TP"] + counts["FP"])
        if counts["TP"] + counts["FP"]
        else None,
        "recall": counts["TP"] / (counts["TP"] + counts["FN"]),
        "all_alert_count": len(findings),
    }


def main():
    directory = ROOT / "artifacts/benchmarks" / ("rule-holdout-" + str(uuid4()))
    source = directory / "source"
    source.mkdir(parents=True)
    labels = []
    for name, vulnerable, body in CASES:
        text = HEADER + body
        path = source / (name + ".py")
        path.write_text(text)
        labels.append(
            {
                "file": path.name,
                "line": next(
                    i + 1
                    for i, line in enumerate(text.splitlines())
                    if "# target" in line
                ),
                "vulnerable": vulnerable,
            }
        )
    knowledge = ROOT / "docs/knowledge/python-codeql.md"
    query = knowledge.read_text().split("```ql\n", 1)[1].split("```", 1)[0]
    dependencies = fixed_dependencies("python")
    pack = directory / "pack"
    prepare_query(pack, "python", query, {}, dependencies)
    log = directory / "execution.log"
    start = time.perf_counter()
    compile_query(pack, log)
    compilation = time.perf_counter() - start
    plan = ScanPlan(
        "python",
        audit_settings.PYTHON_QUERY_PACK,
        "codeql-suites/python-security-extended.qls",
    )
    start = time.perf_counter()
    CodeQLScanner().create_database(source, directory / "database", log, plan)
    extraction = time.perf_counter() - start
    digest = snapshot_digest(source)
    start = time.perf_counter()
    CodeQLScanner().analyze(
        directory / "database", directory / "baseline.sarif", log, plan
    )
    baseline = evaluate(
        labels, parse_sarif(directory / "baseline.sarif", digest), "py/code-injection"
    )
    baseline["scan_seconds"] = time.perf_counter() - start
    report = {
        "scope": "8 original independent examples; manually supplied seed anchor query, NOT AI generated rules",
        "knowledge": str(knowledge.relative_to(ROOT)),
        "query_purpose": "review anchor; deliberately not a complete vulnerability detector",
        "snapshot": digest,
        "dependencies": dependencies,
        "compile_seconds": compilation,
        "extract_seconds": extraction,
        "baseline": baseline,
        "rounds": [],
    }
    for index in range(3):
        start = time.perf_counter()
        findings = run_query(
            directory / "database",
            pack,
            directory / f"round-{index + 1}.sarif",
            log,
            digest,
        )
        row = {
            "round": index + 1,
            "seconds": time.perf_counter() - start,
            "metrics": evaluate(labels, findings),
        }
        report["rounds"].append(row)
        (directory / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2)
        )
        print(json.dumps(row, ensure_ascii=False), flush=True)
    print("REPORT_PATH=" + str(directory / "report.json"))


if __name__ == "__main__":
    main()
