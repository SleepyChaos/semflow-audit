from pathlib import Path

import pytest
from semflow_research.adapters.repository_locator import RepositoryLocator


def test_finds_javascript_definition_in_python_repository(tmp_path):
    template = tmp_path / "templates/form.html"
    template.parent.mkdir()
    template.write_text('<button onclick="submitForm()">Submit</button>\n')
    script = tmp_path / "static/admin/modal.js"
    script.parent.mkdir(parents=True)
    script.write_text(
        "// submitForm()\nexport const submitForm = () => {\n  return true;\n};\n"
    )
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules/hidden.js").write_text("function submitForm() {}")
    (tmp_path / "helper.py").write_text(
        "class Controller:\n    def submitForm(self):\n        pass\n"
    )

    locator = RepositoryLocator(tmp_path, lambda relative: tmp_path / relative)
    result = locator.find_symbol("submitForm", scope=("static", "templates"))
    assert [(hit.file, hit.start_line, hit.kind) for hit in result.matches] == [
        ("static/admin/modal.js", 2, "lexical_definition")
    ]
    assert result.matches[0].language == "javascript"
    matches = locator.search_code("submitForm", file_pattern="static/*.js").matches
    assert {m.file for m in matches} == {"static/admin/modal.js"}
    assert [
        m.file
        for m in locator.find_references("submitForm", scope=("templates",)).matches
    ] == ["templates/form.html"]
    assert locator.find_symbol("submitForm", limit=1).truncated
    assert all(
        not hit.file.startswith("node_modules")
        for hit in locator.find_symbol("submitForm").matches
    )


def test_original_django_snapshot_definition_needs_no_path_hint():
    import os

    import pytest

    source = os.environ.get("SEMFLOW_DJANGOAT_SOURCE")
    if not source:
        pytest.skip("Pinned DjanGoat snapshot unavailable")
    root = Path(source)
    resolver = RepositoryLocator(root, lambda relative: root / relative)
    (hit,) = resolver.find_symbol("submitForm").matches
    assert hit.file == "static/app/javascript/admin/modal.js"
    assert hit.start_line == 30
    assert any(
        r.file == "template/admin/modal.html"
        for r in resolver.find_references("submitForm").matches
    )


def test_guard_rejects_a_truthful_quote_from_an_unrelated_handler(tmp_path):
    from types import SimpleNamespace
    from uuid import uuid4

    import pytest
    from semflow_research.discovery.review_target_scope import guard_operation_scope
    from semflow_research.domain.errors import AuditError

    body = (
        "def dashboard():\n"
        "    return 'dashboard'\n\n"
        "def evaluate():\n"
        "    return 'evaluate'\n"
    )
    target = tmp_path / "app.py"
    target.write_text(body)
    id = uuid4()
    assessment = SimpleNamespace(
        premises=[
            SimpleNamespace(
                premise="operation",
                status="established",
                quote="return 'evaluate'",
                evidence_ids=[id],
            )
        ]
    )
    page = {
        "kind": "code",
        "content": body,
        "reference": {
            "file": "app.py",
            "start_line": 1,
            "end_line": 5,
        },
    }
    evidence = SimpleNamespace(allowed=lambda relative: tmp_path / relative)
    with pytest.raises(AuditError, match="冻结候选"):
        guard_operation_scope(
            evidence,
            {"location": {"file": "app.py", "line": 1}},
            assessment,
            lambda identifiers: [page],
        )


def test_search_bounds_exclude_generated_and_large_files(tmp_path):
    (tmp_path / ".env.js").write_text("function inspectLocal() {}")
    (tmp_path / "dist").mkdir()
    (tmp_path / "dist/bundle.js").write_text("function inspectLocal() {}")
    (tmp_path / "huge.js").write_text("x" * (1024 * 1024 + 1))
    locator = RepositoryLocator(tmp_path, lambda name: tmp_path / name)
    result = locator.find_symbol("inspectLocal")
    assert result.matches == ()
    assert result.truncated
    assert locator.find_symbol("inspectLocal", scope=("dist/bundle.js",)).matches
    assert not locator.find_symbol("missing").matches
    assert not locator.find_paths("../bundle.js").matches
    assert not locator.find_paths("C:/bundle.js").matches


@pytest.mark.parametrize(
    ("property_name", "file", "line", "unproved", "protection"),
    [
        (
            "output_encoding",
            "api.py",
            "return jsonify(message=name)",
            "unsafe_protection",
            "missing",
        ),
        (
            "output_encoding",
            "result.html",
            "{{ message }}",
            "unsafe_protection",
            "contradicted",
        ),
        (
            "output_encoding",
            "views.py",
            'flash("Saved")',
            "input_or_policy",
            "contradicted",
        ),
        (
            "state_integrity",
            "settings.py",
            'MIDDLEWARE = ["CsrfViewMiddleware"]',
            "unsafe_protection",
            "contradicted",
        ),
        (
            "secrets_config",
            "settings.py",
            'CORS(app, origins="*")',
            "input_or_policy",
            "missing",
        ),
    ],
)
def test_navigation_does_not_validate_confirmation_with_an_unclosed_premise(
    property_name, file, line, unproved, protection
):
    from types import SimpleNamespace

    from semflow_research.discovery.discovery_context import validate_premises
    from semflow_research.domain.errors import AuditError

    roles = ("operation", "input_or_policy", "unsafe_protection")
    premises = [
        SimpleNamespace(
            premise=role,
            status=protection if role == unproved else "established",
            evidence_ids=[],
            quote=line,
        )
        for role in roles
    ]
    cited = {"kind": "code", "reference": {"file": file}, "content": line}
    with pytest.raises(AuditError, match="未闭合本地前提"):
        validate_premises(
            SimpleNamespace(
                security_property=property_name,
                premises=premises,
                assessment="supported",
            ),
            {"security_property": property_name, "required_premises": roles},
            {"language": "python", "evidence_gap_contract": "enabled"},
            lambda ids: [cited],
        )
