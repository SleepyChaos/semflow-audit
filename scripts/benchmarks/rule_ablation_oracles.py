"""Evaluator-only variants and reusable real databases; never prompt material."""

import hashlib
import json
import re
from pathlib import Path

from app.adapters.codeql.custom import run_query, write_fixtures
from app.adapters.codeql.scanner import CodeQLScanner
from app.domain.audit import ScanPlan
from app.services.rule_holdouts import dataset


def variant_dataset(identifier):
    original = dataset(identifier)
    fixtures = {}
    for kind, fixture in original["fixtures"].items():
        files, expected = {}, []
        for index, (name, text) in enumerate(fixture["files"].items()):
            new_name = f"variant_{kind}_{index}" + Path(name).suffix
            if original["language"] == "python":
                text = text.replace("def handler():", "def assessment_endpoint():")
                text = re.sub(
                    r"(?m)^( +)return",
                    lambda m: (
                        m[1] + "# independent rename/offset variant\n" + m[1] + "return"
                    ),
                    text,
                )
                text = text.replace(
                    'request.args["value"]', 'request.args["audit_payload"]'
                )
                text = text.replace(
                    "from flask import", "# evaluator-only variant\nfrom flask import"
                )
            else:
                text = text.replace("req.query.value", "req.query.auditPayload")
                text = "// evaluator-only variant\n" + text.replace(
                    "// target", "// target"
                )
            files[new_name] = text
            if kind == "positive":
                expected.extend(
                    {"file": new_name, "line": line}
                    for line, content in enumerate(text.splitlines(), 1)
                    if "# target" in content or "// target" in content
                )
        fixtures[kind] = {"files": files, "expected": expected}
    return {
        **original,
        "fixtures": fixtures,
        "hash": hashlib.sha256(
            json.dumps(fixtures, sort_keys=True).encode()
        ).hexdigest(),
        "meaning": "Unseen identifier/offset micro-variants; same semantic families, not cross-project generalization",
    }


def build_databases(directory, data):
    scanner = CodeQLScanner()
    for kind in ("positive", "negative"):
        root = directory / kind
        write_fixtures(root, data["language"], data["fixtures"][kind])
        cache = directory / (kind + "-fixture-hash.json")
        digest = hashlib.sha256(
            json.dumps(data["fixtures"][kind], sort_keys=True).encode()
        ).hexdigest()
        if cache.exists() and json.loads(cache.read_text()).get("hash") == digest:
            continue
        scanner.create_database(
            root,
            directory / (kind + "-database"),
            directory / "build.log",
            ScanPlan(data["language"], "", ""),
        )
        cache.write_text(json.dumps({"hash": digest}))


def evaluate(directory, pack, data, output):
    output.mkdir(parents=True, exist_ok=True)
    checks = {}
    tp = fp = fn = 0
    for kind in ("positive", "negative"):
        findings = run_query(
            directory / (kind + "-database"),
            pack,
            output / (kind + ".sarif"),
            output / "execution.log",
            "ablation:" + data["hash"],
        )
        actual = {
            (loc["file"], loc["line"])
            for finding in findings
            for loc in finding["locations"]
        }
        expected = {
            (row["file"], row["line"]) for row in data["fixtures"][kind]["expected"]
        }
        tp += len(actual & expected)
        fp += len(actual - expected)
        fn += len(expected - actual)
        checks[kind] = {"expected": sorted(expected), "actual": sorted(actual)}
    return {
        "status": "passed" if not fp and not fn else "failed",
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "checks": checks,
        "dataset_hash": data["hash"],
    }
