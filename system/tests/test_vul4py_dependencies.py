"""Dependency recovery must come from declarations, not guessed PyPI names."""

import pytest
from scripts.benchmarks.vul4py_dependencies import declared_plan


def test_declared_test_extra_and_requirements_are_hashed_without_modification(tmp_path):
    project = tmp_path / "pyproject.toml"
    text = '[project.optional-dependencies]\ntest=["responses==0.25.3", "pytest<9"]\ndev=["unrelated"]\n'
    project.write_text(text)
    (tmp_path / "requirements-dev.txt").write_text("pytest-cov==5.0.0\n")
    plan = declared_plan(tmp_path)
    assert plan["commands"] == [
        "python -m pip install -e '.[test]'",
        "python -m pip install -r requirements-dev.txt",
    ]
    assert set(plan["declarations"]) == {"pyproject.toml", "requirements-dev.txt"}
    assert project.read_text() == text


def test_missing_declarations_do_not_guess_packages(tmp_path):
    (tmp_path / "error.log").write_text(
        "ModuleNotFoundError: No module named 'guess_me'"
    )
    assert declared_plan(tmp_path)["commands"] == []


def test_external_dependency_symlink_is_rejected(tmp_path):
    outside = tmp_path / "outside"
    outside.write_text("[project]\n")
    source = tmp_path / "source"
    source.mkdir()
    (source / "pyproject.toml").symlink_to(outside)
    with pytest.raises(RuntimeError, match="escapes"):
        declared_plan(source)
