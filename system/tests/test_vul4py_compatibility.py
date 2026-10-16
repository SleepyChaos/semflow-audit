"""Collection repairs follow project settings without dropping security tests."""

import json

import pytest
from scripts.benchmarks.vul4py_compatibility import collection_meta, constraints


def test_helper_is_retained_on_disk_but_not_directly_collected(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\npython_files="test_*.py"\n'
    )
    (source / "test_repo.py").write_text("def test_security():\n    assert True\n")
    helper = source / "cat_file.py"
    helper.write_text("import sys\nopen(sys.argv[1])\n")
    logs = tmp_path / "logs"
    meta = {
        "baseline_test_files": ["test_repo.py", "cat_file.py"],
        "new_test_files": ["test_repo.py"],
    }
    original = json.dumps(meta)
    effective = collection_meta(source, meta, logs)
    assert effective["baseline_test_files"] == ["test_repo.py"]
    assert effective["new_test_files"] == meta["new_test_files"]
    assert helper.read_text() == "import sys\nopen(sys.argv[1])\n"
    assert json.dumps(meta) == original


def test_nonmatching_explicit_file_with_assertion_test_is_not_silently_removed(
    tmp_path,
):
    (tmp_path / "security_check.py").write_text(
        "def test_attack():\n    assert False\n"
    )
    with pytest.raises(RuntimeError, match="conflicts"):
        collection_meta(
            tmp_path,
            {
                "baseline_test_files": ["security_check.py"],
                "new_test_files": ["security_check.py"],
            },
            tmp_path / "logs",
        )


def test_constraints_do_not_change_warning_filters_or_project_sources(
    tmp_path, monkeypatch
):
    case = tmp_path / "CVE-example"
    case.mkdir()
    monkeypatch.delenv("PIP_CONSTRAINT", raising=False)
    constraints(case, {"projects": {case.name: {"constraints": {"click": "8.1.7"}}}})
    import os

    path = case / "compatibility-constraints.txt"
    assert path.read_text() == "click==8.1.7\n"
    assert os.environ["PIP_CONSTRAINT"] == str(path)
    assert not (case / "pytest.ini").exists()
