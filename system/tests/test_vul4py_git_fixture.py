"""Evaluator history restoration leaves vulnerable tracked bytes unchanged."""

import shutil
import subprocess

import pytest
from scripts.benchmarks.vul4py_git_fixture import configure_safe_paths, restore


def git(*args):
    return subprocess.check_output(["git", *map(str, args)], text=True).strip()


def test_native_history_restored_without_checking_out_fixed_source(
    tmp_path, monkeypatch
):
    original = tmp_path / "upstream"
    git("init", original)
    code = original / "app.py"
    code.write_text("value = eval(input())\n")
    git("-C", original, "add", "app.py")
    git(
        "-C",
        original,
        "-c",
        "user.name=Fixture",
        "-c",
        "user.email=fixture@example.invalid",
        "commit",
        "-m",
        "original",
    )
    vulnerable = git("-C", original, "rev-parse", "HEAD")
    code.write_text("value = int(input())\n")
    git("-C", original, "add", "app.py")
    git(
        "-C",
        original,
        "-c",
        "user.name=Fixture",
        "-c",
        "user.email=fixture@example.invalid",
        "commit",
        "-m",
        "fixed",
    )
    case = tmp_path / "case"
    source = case / "vulnerable"
    source.mkdir(parents=True)
    (source / "app.py").write_text("value = eval(input())\n")
    logs = case / "logs"
    logs.mkdir()
    monkeypatch.setenv("GIT_CONFIG_COUNT", "0")
    for index in range(3):
        monkeypatch.setenv(f"GIT_CONFIG_KEY_{index}", "safe.directory")
        monkeypatch.setenv(f"GIT_CONFIG_VALUE_{index}", str(case))
    configure_safe_paths(case)
    meta = {
        "repo_url": str(original),
        "versions": {"vulnerable": {"git_ref": vulnerable}},
    }
    restore(case, source, "vulnerable", meta, logs)
    assert (source / "app.py").read_text() == "value = eval(input())\n"
    assert git("-C", source, "rev-parse", "HEAD") == vulnerable
    assert git("-C", source, "diff", "--", "app.py") == ""
    restore(case, source, "vulnerable", meta, logs)
    (source / "app.py").write_text("tampered\n")
    with pytest.raises(RuntimeError, match="source changed"):
        restore(case, source, "vulnerable", meta, logs)


def test_missing_submodule_is_restored_at_gitlink_without_changing_main_code(
    tmp_path, monkeypatch
):
    dependency = tmp_path / "dependency"
    git("init", dependency)
    (dependency / "dep.py").write_text("dependency = 1\n")
    git("-C", dependency, "add", "dep.py")
    git(
        "-C",
        dependency,
        "-c",
        "user.name=Fixture",
        "-c",
        "user.email=fixture@example.invalid",
        "commit",
        "-m",
        "dependency",
    )
    upstream = tmp_path / "upstream"
    git("init", upstream)
    (upstream / "app.py").write_text("value = eval(input())\n")
    git(
        "-C",
        upstream,
        "-c",
        "protocol.file.allow=always",
        "submodule",
        "add",
        dependency,
        "vendor/dep",
    )
    git("-C", upstream, "add", ".")
    git(
        "-C",
        upstream,
        "-c",
        "user.name=Fixture",
        "-c",
        "user.email=fixture@example.invalid",
        "commit",
        "-m",
        "original",
    )
    reference = git("-C", upstream, "rev-parse", "HEAD")
    case = tmp_path / "case"
    source = case / "vulnerable"
    source.mkdir(parents=True)
    shutil.copyfile(upstream / "app.py", source / "app.py")
    shutil.copyfile(upstream / ".gitmodules", source / ".gitmodules")
    logs = case / "logs"
    logs.mkdir()
    monkeypatch.setenv("GIT_CONFIG_COUNT", "0")
    for index in range(3):
        monkeypatch.setenv(f"GIT_CONFIG_KEY_{index}", "safe.directory")
        monkeypatch.setenv(f"GIT_CONFIG_VALUE_{index}", str(case))
    configure_safe_paths(case)
    restore(
        case,
        source,
        "vulnerable",
        {"repo_url": str(upstream), "versions": {"vulnerable": {"git_ref": reference}}},
        logs,
        restore_submodules=True,
    )
    assert (source / "app.py").read_text() == "value = eval(input())\n"
    assert (source / "vendor/dep/dep.py").read_text() == "dependency = 1\n"
    assert git("-C", source / "vendor/dep", "rev-parse", "HEAD") == git(
        "-C", dependency, "rev-parse", "HEAD"
    )
    assert git("-C", source, "rev-parse", "HEAD") == reference
    assert git("-C", source, "diff", "--", "app.py") == ""
