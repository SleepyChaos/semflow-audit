"""Maintained starting rules from the installed, pinned CodeQL query packs."""

import re

from app.core.audit_config import audit_settings

CATALOG = {
    "python-eval": (
        "python",
        "eval",
        "CWE-094/CodeInjection.ql",
        "基础规则 · Python 代码注入",
    ),
    "python-sql": (
        "python",
        "sql",
        "CWE-089/SqlInjection.ql",
        "基础规则 · Python SQL 注入",
    ),
    "javascript-xss": (
        "javascript",
        "xss",
        "CWE-079/ReflectedXss.ql",
        "基础规则 · JavaScript 反射型 XSS",
    ),
}


def baseline_definition(identifier):
    language, operation, relative, title = CATALOG[identifier]
    specification = (
        audit_settings.PYTHON_QUERY_PACK
        if language == "python"
        else audit_settings.JAVASCRIPT_QUERY_PACK
    )
    name, version = specification.split("@")
    path = audit_settings.CODEQL_PACK_PATH / name / version / "Security" / relative
    original = path.read_text()
    query = re.sub(r"@id\s+[^\n]+", f"@id custom/baseline/{identifier}-v1", original)
    query = re.sub(r"@name\s+[^\n]+", f"@name {title}", query)
    return {
        "id": identifier,
        "language": language,
        "title": title,
        "query": query,
        "holdout_id": f"{language}-{operation}-vulnerability_detector-v1",
        "source": {"pack": specification, "path": f"Security/{relative}"},
        "fixtures": fixtures(language, operation),
    }


def fixtures(language, operation):
    if language == "javascript":
        header = "const express = require('express');\nconst server = express();\nserver.get('/search', (request, response) => {\n"
        positive = header + "  response.send(request.query.search); // target\n});\n"
        negative = header + "  response.json({search: request.query.search});\n});\n"
        extension = "js"
    else:
        header = "from flask import Flask, request\nserver = Flask(__name__)\n@server.post('/process')\ndef process():\n"
        if operation == "eval":
            positive = (
                header
                + "    expression = request.form['expression']\n    return str(eval(expression)) # target\n"
            )
            negative = header + "    return str(eval('20 + 22'))\n"
        else:
            header += (
                "    import sqlite3\n    connection = sqlite3.connect(':memory:')\n"
            )
            positive = (
                header
                + "    return connection.execute('SELECT name FROM accounts WHERE name=' + request.form['name']).fetchall() # target\n"
            )
            negative = (
                header
                + "    return connection.execute('SELECT name FROM accounts WHERE name=?', (request.form['name'],)).fetchall()\n"
            )
        extension = "py"
    positive_file, negative_file = f"unsafe.{extension}", f"safe.{extension}"
    expected = [
        {"file": positive_file, "line": line}
        for line, content in enumerate(positive.splitlines(), 1)
        if "# target" in content or "// target" in content
    ]
    return {
        "positive": {"files": {positive_file: positive}, "expected": expected},
        "negative": {"files": {negative_file: negative}, "expected": []},
    }
