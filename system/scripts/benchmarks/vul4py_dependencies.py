"""Install only project-declared test extras, preserving declaration hashes."""

import hashlib
import shlex

import tomllib
from scripts.benchmarks.mechanical_pipeline import save

EXTRAS = ("test", "tests", "testing", "dev", "develop", "development")
REQUIREMENTS = (
    "requirements/test.txt",
    "requirements/tests.txt",
    "requirements/dev.txt",
    "requirements/development.txt",
    "requirements-test.txt",
    "requirements-tests.txt",
    "requirements-dev.txt",
    "test-requirements.txt",
    "dev-requirements.txt",
)


def declared_plan(source):
    declarations = []
    commands = []
    pyproject = source / "pyproject.toml"
    if pyproject.is_file():
        if pyproject.is_symlink() or not pyproject.resolve().is_relative_to(
            source.resolve()
        ):
            raise RuntimeError("Test dependency declaration escapes project")
        try:
            project = tomllib.loads(pyproject.read_text())
        except tomllib.TOMLDecodeError:
            project = {}
        extras = project.get("project", {}).get("optional-dependencies", {})
        chosen = next((name for name in EXTRAS if extras.get(name)), None)
        if chosen:
            declarations.append(pyproject)
            commands.append("python -m pip install -e " + shlex.quote(f".[{chosen}]"))
    for name in REQUIREMENTS:
        path = source / name
        if path.is_file():
            if path.is_symlink() or not path.resolve().is_relative_to(source.resolve()):
                raise RuntimeError("Test dependency declaration escapes project")
            declarations.append(path)
            commands.append("python -m pip install -r " + shlex.quote(name))
            break
    return {
        "commands": commands,
        "declarations": {
            str(p.relative_to(source)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in declarations
        },
        "status": "declared" if commands else "no_supported_test_declaration",
        "tests_and_assertions_modified": False,
    }


def install(official, tools, source, logs):
    plan = declared_plan(source)
    save(logs / f"test-dependency-plan-{source.name}.json", plan)
    for index, command in enumerate(plan["commands"]):
        official.run_in_venv(
            tools,
            command,
            source,
            logs / f"test-dependencies-{source.name}-{index}.log",
            check=True,
        )
    official.run_in_venv(
        tools,
        "python -m pip freeze",
        source,
        logs / f"environment-freeze-{source.name}.log",
        check=True,
    )
