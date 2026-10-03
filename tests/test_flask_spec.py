from uuid import uuid4

import pytest
from app.adapters.codeql.flask_spec import RouteShortcut, generate_flask_spec
from app.domain.audit import AuditError
from pydantic import ValidationError


def test_route_grammar_rejects_unreviewed_methods_and_symbols():
    for owner, method in (
        ("OtherReceiver", "get"),
        ("Flask", "delete"),
        ("Flask", 'get") select 1 //'),
    ):
        with pytest.raises(ValidationError):
            RouteShortcut(owner=owner, method=method, evidence_id=uuid4())


def test_each_route_symbol_requires_its_actual_retrieved_document():
    identifier = uuid4()

    class Provider:
        def generate(self, purpose, context, schema):
            return schema.model_validate(
                {
                    "language": "python",
                    "operation": "xss",
                    "purpose": "vulnerability_detector",
                    "title": "route model",
                    "coverage_analysis": "Requires documented registration semantics.",
                    "shortcuts": [
                        {
                            "owner": "Blueprint",
                            "method": "post",
                            "evidence_id": str(identifier),
                        }
                    ],
                    "knowledge_ids": [str(identifier)],
                    "positive": {
                        "files": {"a.py": "pass\n"},
                        "expected": [{"file": "a.py", "line": 1}],
                    },
                    "negative": {"files": {"b.py": "pass\n"}, "expected": []},
                }
            )

    with pytest.raises(AuditError, match="实际检索证据"):
        generate_flask_spec(
            Provider(),
            {
                "language": "python",
                "purpose": "vulnerability_detector",
                "knowledge": [
                    {
                        "id": str(identifier),
                        "content": "flask.Flask.get is documented; unrelated API.",
                    }
                ],
            },
        )
