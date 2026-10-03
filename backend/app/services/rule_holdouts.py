"""Server-owned independent fixtures, never supplied to rule-generation prompts."""

import hashlib
import json

from app.adapters.codeql.custom import validate_fixtures
from app.domain.audit import AuditError

PY_HEADER = 'from flask import Flask, request\napp = Flask(__name__)\n@app.get("/")\ndef handler():\n'
JS_HEADER = 'const express = require("express");\nconst app = express();\napp.get("/", (req,res) => {\n'
OPS = {
    ("python", "eval"): (
        '    return str(eval(request.args["value"])) # target\n',
        '    return str(eval("1+2")) # target\n',
        '    return str(int(request.args["value"]))\n',
    ),
    ("python", "sql"): (
        '    import sqlite3\n    db = sqlite3.connect(":memory:")\n    db.execute("SELECT name FROM users WHERE name=" + request.args["value"]) # target\n',
        '    import sqlite3\n    db = sqlite3.connect(":memory:")\n    db.execute("SELECT name FROM users WHERE name=?", (request.args["value"],)) # target\n',
        '    return str(int(request.args["value"]))\n',
    ),
    ("python", "xss"): (
        '    return request.args["value"] # target\n',
        '    from markupsafe import escape\n    return str(escape(request.args["value"])) # target\n',
        "    pass\n",
    ),
    ("javascript", "eval"): (
        "res.json({value:eval(req.query.value)}); // target\n",
        'res.json({value:eval("1+2")}); // target\n',
        "res.json({value:Number(req.query.value)});\n",
    ),
    ("javascript", "sql"): (
        'const db=require("mysql").createConnection({});\ndb.query("SELECT name FROM users WHERE name="+req.query.value); // target\n',
        'const db=require("mysql").createConnection({});\ndb.query("SELECT name FROM users WHERE name=?",[req.query.value]); // target\n',
        "res.json({value:Number(req.query.value)});\n",
    ),
    ("javascript", "xss"): (
        "res.send(req.query.value); // target\n",
        "res.json({value:req.query.value}); // target\n",
        "const ignored = 0;\n",
    ),
}


def source(language, body):
    return (
        (PY_HEADER if language == "python" else JS_HEADER)
        + body
        + ("});\n" if language == "javascript" else "")
    )


def dataset(identifier: str) -> dict:
    registry = {}
    for (language, operation), (vulnerable, safe_sink, no_sink) in OPS.items():
        extension = "py" if language == "python" else "js"
        for purpose in ("review_anchor", "vulnerability_detector"):
            name = f"{language}-{operation}-{purpose}-v1"
            positives = {f"positive.{extension}": source(language, vulnerable)}
            negatives = {
                f"negative.{extension}": source(
                    language,
                    safe_sink if purpose == "vulnerability_detector" else no_sink,
                )
            }
            if purpose == "review_anchor":
                positives[f"constant_or_safe.{extension}"] = source(language, safe_sink)
            if operation == "eval":
                shadow = (
                    '    def eval(value):\n        return value\n    return str(eval(request.args["value"])) # target\n'
                    if language == "python"
                    else "function eval(value){return value;}\nres.json({value:eval(req.query.value)}); // target\n"
                )
                if purpose == "review_anchor":
                    positives[f"shadowed.{extension}"] = source(language, shadow)
                else:
                    negatives[f"shadowed.{extension}"] = source(language, shadow)
                    alias = (
                        '    execute = eval\n    return str(execute(request.args["value"])) # target\n'
                        if language == "python"
                        else "const execute=eval;\nres.json({value:execute(req.query.value)}); // target\n"
                    )
                    positives[f"aliased.{extension}"] = source(language, alias)
            expected = [
                {"file": file, "line": index}
                for file, text in positives.items()
                for index, line in enumerate(text.splitlines(), 1)
                if "# target" in line or "// target" in line
            ]
            fixtures = {
                "positive": {"files": positives, "expected": expected},
                "negative": {"files": negatives, "expected": []},
            }
            registry[name] = {
                "id": name,
                "language": language,
                "purpose": purpose,
                "operation": operation,
                "fixtures": fixtures,
                "meaning": "original independent micro-fixtures; not a large-project accuracy claim",
                "hash": hashlib.sha256(
                    json.dumps(fixtures, sort_keys=True).encode()
                ).hexdigest(),
            }
    if identifier not in registry:
        raise AuditError("独立样本集不存在")
    return registry[identifier]


def catalog():
    return [
        {
            k: v
            for k, v in dataset(f"{language}-{operation}-{purpose}-v1").items()
            if k != "fixtures"
        }
        for language, operation in OPS
        for purpose in ("review_anchor", "vulnerability_detector")
    ]


def validation_fingerprint(rule) -> str:
    materials = {
        "query": rule.query,
        "modules": rule.modules,
        "dependencies": rule.dependencies,
        "purpose": rule.purpose,
        "fixtures": rule.fixtures,
        "holdout_id": rule.holdout_id,
    }
    return hashlib.sha256(json.dumps(materials, sort_keys=True).encode()).hexdigest()


def evaluate_holdout(rule, directory, pack):
    if not rule.holdout_id:
        return {"status": "not_evaluated", "meaning": "No independent dataset selected"}
    data = dataset(rule.holdout_id)
    if (data["language"], data["purpose"]) != (rule.language, rule.purpose):
        raise AuditError("独立样本集语言或用途不匹配")
    result = validate_fixtures(directory, pack, rule.language, data["fixtures"])
    return {
        **result,
        "dataset_id": data["id"],
        "dataset_hash": data["hash"],
        "meaning": data["meaning"],
    }


def check_modern_validation(rule):
    if rule.purpose == "unknown":
        return  # Historical v1 rules retain their old verification semantics.
    if rule.validation.get("validation_fingerprint") != validation_fingerprint(rule):
        raise AuditError("规则依赖/用途/样本内容已变化，必须重新验收")
    independent = rule.validation.get("independent_holdout", {})
    if independent.get("status") != "passed" or not rule.holdout_id:
        raise AuditError("规则发布需要独立样本验收")
    if independent.get("dataset_hash") != dataset(rule.holdout_id)["hash"]:
        raise AuditError("独立样本集已变化，必须重新验收")
