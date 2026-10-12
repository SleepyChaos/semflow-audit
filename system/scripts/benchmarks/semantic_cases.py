"""Fresh development comparisons, not a standard or independent paper benchmark."""

CASES = {
    "arithmetic": {
        "file": "engine.py",
        "line": 2,
        "cwe": "CWE-94",
        "description": "External input reaches dynamic code execution in calculate; eliminate code execution without deleting legitimate behavior.",
        "files": {
            "engine.py": "def calculate(expression):\n    return eval(expression)\n",
            "client.py": "from engine import calculate\ndef preview():\n    return [calculate('1+2'), calculate('9-4'), calculate('1.5+2.5')]\n",
            "README.md": "# Arithmetic preview\nBusiness contract: accept integer/decimal literals, unary signs, parentheses, addition and subtraction. Return the arithmetic result. Invalid constructs raise ValueError. Calls, names and attribute access are not legitimate operations.\n",
        },
        "functional_test": """from engine import calculate
def test_arithmetic_contract():
    for text, result in [('12',12), ('1+2',3), ('9-4',5), ('1.5+2.5',4.0), ('-(1+2)',-3)]:
        assert calculate(text) == result
""",
    },
    "document_path": {
        "file": "storage.py",
        "line": 3,
        "cwe": "CWE-22",
        "description": "The path resolver accepts user input without enforcing the configured document root; enforce containment while retaining legitimate document resolution.",
        "files": {
            "storage.py": "from pathlib import Path\ndef resolve_document(root, name):\n    return Path(root) / name\n",
            "download.py": "from storage import resolve_document\ndef download(root, name):\n    return resolve_document(root, name).read_text()\n",
            "README.md": "# Document workspace\nThe root is supplied by trusted application configuration. Names can be relative or absolute. Absolute paths INSIDE root are legitimate. Return a Path object. Nested documents and the root itself are allowed. Resolution outside root raises ValueError.\n",
        },
        "functional_test": """from pathlib import Path
from storage import resolve_document
def test_document_contract():
    root = Path('/tmp/documents')
    assert resolve_document(root, 'a.txt') == root / 'a.txt'
    assert resolve_document(root, 'nested/b.txt') == root / 'nested/b.txt'
    assert resolve_document(root, '/tmp/documents/a.txt') == root / 'a.txt'
    assert resolve_document(root, '.') == root
""",
    },
}

RULE_CASES = {
    "event_eval": {
        "file": "handler.py",
        "line": 4,
        "cwe": "CWE-94",
        "files": {
            "handler.py": "import events_api\ndef handle():\n    value = events_api.fetch_event()\n    return eval(value)\n",
            "README.md": "# Event processing\nevents_api.fetch_event returns an untrusted external event string. handle interprets it.\n",
        },
        "description": "Untrusted external event returned by events_api.fetch_event reaches eval in handle; baseline framework coverage omits the custom events API.",
        "requirement": "Generate a Python CWE-94 code-injection vulnerability_detector: events_api.fetch_event() returns untrusted external text which may flow through variables/helpers to eval. Model this exact source API and use dataflow to the eval sink; safe int conversion must not alert. Use CodeInjectionQuery/Customizations and fixed API declarations when appropriate. No file/line or literal keyword detector.",
        "holdout": {
            "positive": {
                "files": {
                    "renamed.py": "import events_api\ndef forward(v):\n    return v\ndef other():\n    return eval(forward(events_api.fetch_event()))\n"
                },
                "expected": [{"file": "renamed.py", "line": 5}],
            },
            "negative": {
                "files": {
                    "safe.py": "import events_api\ndef other():\n    return int(events_api.fetch_event())\n"
                },
                "expected": [],
            },
        },
    },
}
