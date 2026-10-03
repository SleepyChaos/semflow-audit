from pathlib import Path
from uuid import uuid4
import pytest
from app.adapters.repair.patches import apply_changes
from app.adapters.codeql.custom import query_digest, write_fixtures
from app.contracts.stages import ProposedChange
from app.domain.audit import AuditError
from app.persistence.knowledge_models import RuleVersion
from app.services.rules import publish_rule


def change(file="app.py", old="eval(input())", new="int(input())"):
    return ProposedChange(
        file=file,
        old_text=old,
        new_text=new,
        reason="Restrict input interpretation to a numeric conversion.",
    )


def test_patch_isolation_and_exact_diff(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "app.py").write_text("value = eval(input())\n")
    diff = apply_changes(source, tmp_path / "patched", [change()], ["app.py"])
    assert "-value = eval(input())" in diff and "+value = int(input())" in diff
    assert (source / "app.py").read_text() == "value = eval(input())\n"
    assert (tmp_path / "patched/app.py").read_text() == "value = int(input())\n"


@pytest.mark.parametrize(
    "path", ["../outside.py", ".env", "tests/test_app.py", "/tmp/outside.py"]
)
def test_patch_rejects_unapproved_paths(tmp_path, path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "app.py").write_text("eval(input())")
    with pytest.raises(AuditError):
        apply_changes(source, tmp_path / "patched", [change(file=path)], ["app.py"])
    assert not (tmp_path / "patched").exists()


def test_ambiguous_replacement_does_not_apply(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "app.py").write_text("eval(input());eval(input())")
    with pytest.raises(AuditError, match="精确匹配一次"):
        apply_changes(source, tmp_path / "patched", [change()], ["app.py"])
    assert not (tmp_path / "patched").exists()


def test_rules_require_approved_tests_and_unchanged_query():
    rule = RuleVersion(
        owner_id=uuid4(),
        audit_id=uuid4(),
        stage_id=uuid4(),
        language="python",
        title="test",
        strategy="new_query",
        query="select 1",
        query_hash=query_digest("select 1", {}),
    )
    with pytest.raises(AuditError):
        publish_rule(rule)
    rule.fixtures_approved = True
    rule.status = "validated"
    rule.validation = {"status": "passed", "query_hash": rule.query_hash}
    rule.query = "select 2"
    with pytest.raises(AuditError, match="内容已变化"):
        publish_rule(rule)
    rule.query = "select 1"
    publish_rule(rule)
    assert rule.status == "published" and rule.published_at is not None


def test_fixture_expectations_are_real_positions(tmp_path):
    with pytest.raises(AuditError, match="预期行"):
        write_fixtures(
            tmp_path,
            "python",
            {
                "files": {"positive.py": "eval(input())"},
                "expected": [{"file": "positive.py", "line": 99}],
            },
        )
    with pytest.raises(AuditError):
        write_fixtures(
            tmp_path,
            "python",
            {"files": {"../evil.py": "eval(input())"}, "expected": []},
        )


@pytest.mark.parametrize(
    "name,content",
    [("bad.py", "eval("), ("bad.js", "function {"), ("bad.ts", "const x: = 1")],
)
def test_invalid_fixture_syntax_is_not_a_passing_negative(tmp_path, name, content):
    language = "python" if name.endswith(".py") else "javascript"
    with pytest.raises(AuditError, match="语法无效"):
        write_fixtures(tmp_path, language, {"files": {name: content}, "expected": []})
