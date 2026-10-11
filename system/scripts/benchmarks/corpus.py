"""Original paired micro-corpus; deliberately small, not a standard benchmark."""

from pathlib import Path


def write_corpus(root: Path, language: str) -> list[dict]:
    root.mkdir(parents=True, exist_ok=True)
    labels = []
    if language == "python":
        header = 'from flask import Flask, request\nimport os, sqlite3\napp = Flask(__name__)\n@app.get("/")\ndef handler():\n    value = request.args["value"]\n'
        bodies = {
            "eval": (
                "094",
                "    return str(eval(value))",
                "    return str(int(value))",
            ),
            "command": (
                "078",
                '    return str(os.system("echo " + value))',
                "    return str(len(value))",
            ),
            "sql": (
                "089",
                '    return str(sqlite3.connect(":memory:").execute("SELECT * FROM users WHERE name = \'" + value + "\'"))',
                '    return str(sqlite3.connect(":memory:").execute("SELECT * FROM users WHERE name = ?", (value,)))',
            ),
        }
        extension = "py"
    else:
        header = 'const express = require("express");\nconst cp = require("child_process");\nconst mysql = require("mysql");\nconst app = express();\nconst db = mysql.createConnection({});\napp.get("/", (req, res) => {\n  const value = req.query.value;\n'
        bodies = {
            "eval": (
                "094",
                "  res.send(String(eval(value)));",
                "  res.send(String(Number(value)));",
            ),
            "command": (
                "078",
                '  cp.exec("echo " + value, (err, out) => res.send(out));',
                "  res.send(String(value.length));",
            ),
            "sql": (
                "089",
                '  db.query("SELECT * FROM users WHERE name = \'" + value + "\'", (err, rows) => res.send(rows));',
                '  db.query("SELECT * FROM users WHERE name = ?", [value], (err, rows) => res.send(rows));',
            ),
        }
        extension = "js"
    for kind, (cwe, positive, negative) in bodies.items():
        for vulnerable, body in [(True, positive), (False, negative)]:
            file = f"{kind}_{'positive' if vulnerable else 'negative'}.{extension}"
            source = header + body + "\n" + ("});\n" if language != "python" else "")
            (root / file).write_text(source)
            labels.append(
                {
                    "file": file,
                    "line": len(header.splitlines()) + 1,
                    "cwe": cwe,
                    "vulnerable": vulnerable,
                }
            )
    return labels


def write_repair_cases(root: Path) -> list[dict]:
    """Three supplied patches distinguish security from preserving arithmetic behavior."""
    implementations = {
        "unsafe_eval": "    return eval(expression)\n",
        "secure_but_breaks_behavior": "    return int(expression)\n",
        "bounded_arithmetic": """    node = ast.parse(expression, mode="eval").body
    def walk(item):
        if isinstance(item, ast.Constant) and type(item.value) is int:
            return item.value
        if isinstance(item, ast.BinOp) and isinstance(item.op, (ast.Add, ast.Sub)):
            left, right = walk(item.left), walk(item.right)
            return left + right if isinstance(item.op, ast.Add) else left - right
        raise ValueError("unsupported expression")
    return walk(node)
""",
    }
    tests = """import pytest
from calculator import calculate

def test_integer():
    assert calculate("12") == 12

def test_addition():
    assert calculate("1+2") == 3

def test_subtraction():
    assert calculate("9-4") == 5

def test_security_disallows_calls():
    with pytest.raises(ValueError):
        calculate("len('abc')")
"""
    result = []
    for name, body in implementations.items():
        directory = root / name
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "calculator.py").write_text(
            "import ast\ndef calculate(expression):\n" + body
        )
        (directory / "test_calculator.py").write_text(tests)
        result.append(
            {
                "name": name,
                "workspace": str(directory),
                "expected_all_tests_pass": name == "bounded_arithmetic",
            }
        )
    return result
