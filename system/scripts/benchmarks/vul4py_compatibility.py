"""Versioned environment constraints and project-native baseline collection."""

import ast
import configparser
import fnmatch
import os
import shlex

import tomllib
from scripts.benchmarks.mechanical_pipeline import save


def constraints(case, profile):
    selected = profile.get("projects", {}).get(case.name, {})
    if selected.get("restore_git_history"):
        from scripts.benchmarks.vul4py_git_fixture import configure_safe_paths

        configure_safe_paths(case)
    pins = selected.get("constraints", {})
    if not pins:
        return
    path = case / "compatibility-constraints.txt"
    path.write_text(
        "".join(f"{name}=={version}\n" for name, version in sorted(pins.items()))
    )
    os.environ["PIP_CONSTRAINT"] = str(path)


def patterns(source):
    pyproject = source / "pyproject.toml"
    if pyproject.is_file():
        options = (
            tomllib.loads(pyproject.read_text())
            .get("tool", {})
            .get("pytest", {})
            .get("ini_options", {})
        )
        if options.get("python_files"):
            value = options["python_files"]
            return shlex.split(value) if isinstance(value, str) else value
    for name, section in (("pytest.ini", "pytest"), ("setup.cfg", "tool:pytest")):
        path = source / name
        if path.is_file():
            config = configparser.ConfigParser(interpolation=None)
            config.read(path)
            if config.has_option(section, "python_files"):
                return shlex.split(config.get(section, "python_files"))
    return ["test_*.py", "*_test.py"]


def collection_meta(source, meta, logs):
    naming = patterns(source)
    retained, excluded = [], []
    for name in meta["baseline_test_files"]:
        path = source / name.split("::", 1)[0]
        if (
            not path.exists()
            or path.is_dir()
            or any(fnmatch.fnmatch(path.name, pattern) for pattern in naming)
        ):
            retained.append(name)
            continue
        if path.suffix == ".py":
            # Never quietly drop an explicitly named file that contains test cases.
            tree = ast.parse(path.read_text(), filename=str(path))
            if any(
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name.startswith("test")
                for node in ast.walk(tree)
            ):
                raise RuntimeError(
                    f"Explicit test conflicts with project naming: {name}"
                )
        excluded.append(
            {
                "file": name,
                "reason": "not a project-configured test filename; retained on disk for fixtures",
            }
        )
    if not retained:
        raise RuntimeError("Project collection would remove all baseline targets")
    effective = {**meta, "baseline_test_files": retained}
    save(
        logs / f"collection-{source.name}.json",
        {
            "python_files": naming,
            "original_baseline_files": meta["baseline_test_files"],
            "effective_baseline_files": retained,
            "not_directly_collected": excluded,
            "security_files_unchanged": effective["new_test_files"]
            == meta["new_test_files"],
            "assertions_modified": False,
        },
    )
    return effective
