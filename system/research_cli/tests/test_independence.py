"""CLI/package boundaries are verified without relying on an available platform."""

import ast
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from research_cases import scan_spec

SYSTEM = Path(__file__).resolve().parents[2]
SOURCES = [SYSTEM / name / "src" for name in ("contracts", "research", "research_cli")]
GUARD = """
import importlib.abc, sys
class NoPlatform(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'app', 'fastapi', 'celery', 'sqlmodel', 'pydantic_settings'}:
            raise RuntimeError('Forbidden platform import: ' + fullname)
sys.meta_path.insert(0, NoPlatform())
from semflow_research.public import discovery, repair, rules
from semflow_cli.main import main
raise SystemExit(main(sys.argv[1:]))
"""


def run_cli(tmp_path, *arguments, import_all=False):
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("AI_", "DATABASE_", "REDIS_", "PROJECT_"))
    }
    environment["PYTHONPATH"] = os.pathsep.join(map(str, SOURCES))
    environment["HAYSTACK_TELEMETRY_ENABLED"] = "false"
    script = GUARD
    if import_all:
        script = script.replace(
            "from semflow_cli.main import main",
            "import pkgutil, semflow_research\nfor module in pkgutil.walk_packages(semflow_research.__path__, 'semflow_research.'):\n    __import__(module.name)\nfrom semflow_cli.main import main",
        )
    return subprocess.run(
        [sys.executable, "-c", script, *arguments],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def test_every_extracted_module_imports_with_platform_imports_blocked(tmp_path):
    (tmp_path / ".env").write_text(
        "DATABASE_URL=invalid\nAI_API_KEY=must-not-load-this-file\n"
    )
    result = run_cli(tmp_path, "capabilities", import_all=True)
    assert result.returncode == 0, result.stderr
    assert "must-not-load-this-file" not in result.stdout + result.stderr
    capabilities = json.loads(result.stdout)
    assert capabilities["modules"]["discovery"]["implemented"] == [
        "scan",
        "scout",
        "review",
        "discover",
    ]
    assert capabilities["delivery_status"] == "completed"
    assert capabilities["acceptance_scope"] == "core_cli_web_boundaries"
    for module in capabilities["modules"].values():
        assert set(module["implemented"]) == set(module["declared"])
        assert set(module["implemented"]).isdisjoint(module["experimental"])
    repair = capabilities["modules"]["repair"]
    assert repair["implemented_engines"] == ["native", "openhands"]
    assert set(repair["implemented_engines"]).isdisjoint(repair["experimental_engines"])
    rules = capabilities["modules"]["rules"]
    assert rules["implemented_methods"] == ["8"]
    assert set(rules["implemented_methods"]).isdisjoint(rules["experimental_methods"])


def test_help_schema_and_capabilities_without_platform_imports_or_env(tmp_path):
    (tmp_path / ".env").write_text(
        "DATABASE_URL=deliberately-invalid\nAI_API_KEY=do-not-load-this\n"
    )
    assert run_cli(tmp_path, "--help").returncode == 0
    for kind in (
        "run",
        "result",
        "event",
        "bundle_index",
        "candidate_bundle",
        "evidence_bundle",
        "approval_request",
        "checkpoint",
    ):
        process = run_cli(tmp_path, "schema", "--kind", kind)
        assert process.returncode == 0, process.stderr
        from jsonschema import Draft202012Validator

        Draft202012Validator.check_schema(json.loads(process.stdout))
    capabilities = run_cli(tmp_path, "capabilities")
    assert capabilities.returncode == 0, capabilities.stderr
    assert set(json.loads(capabilities.stdout)["modules"]) == {
        "discovery",
        "repair",
        "rules",
    }


def test_validation_is_explicitly_structural_and_does_not_create_execution(tmp_path):
    path = tmp_path / "spec.json"
    path.write_text(json.dumps(scan_spec()))
    result = run_cli(tmp_path, "validate", "--spec", str(path))
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["scope"] == "contract_structure_only"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["spec.json"]


def test_invalid_input_does_not_echo_credentials_or_claim_success(tmp_path):
    value = scan_spec()
    value["api_key"] = "sensitive-test-marker-must-not-echo"
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(value))
    result = run_cli(tmp_path, "validate", "--spec", str(path))
    assert result.returncode == 2 and not result.stdout
    assert json.loads(result.stderr)["code"] == "invalid_contract"
    assert value["api_key"] not in result.stderr


@pytest.mark.parametrize("package", ["contracts", "research", "research_cli"])
def test_source_dependencies_obey_the_independent_package_boundary(package):
    violations = []
    for path in (SYSTEM / package / "src").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            modules = []
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                modules = [node.module or ""]
            for module in modules:
                if module.split(".")[0] in {
                    "app",
                    "fastapi",
                    "celery",
                    "sqlmodel",
                    "pydantic_settings",
                }:
                    violations.append((str(path), node.lineno, module))
                if (
                    package == "research_cli"
                    and module.startswith("semflow_research")
                    and not module.startswith("semflow_research.public")
                ):
                    violations.append((str(path), node.lineno, module))
                if package == "contracts" and module.startswith(
                    ("semflow_research", "semflow_cli", "langgraph")
                ):
                    violations.append((str(path), node.lineno, module))
    assert violations == []


def test_research_services_never_import_routes_or_task_delivery():
    violations = []
    for path in (SYSTEM / "backend/app/services").glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
                ("app.api", "app.jobs")
            ):
                violations.append((path.name, node.lineno, node.module))
    assert violations == []


def test_platform_bridge_imports_only_public_kernel_interfaces():
    violations = []
    for path in (SYSTEM / "backend/app/research_bridge").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            modules = (
                [alias.name for alias in node.names]
                if isinstance(node, ast.Import)
                else [node.module or ""]
                if isinstance(node, ast.ImportFrom)
                else []
            )
            for module in modules:
                if module.startswith("semflow_research") and not module.startswith(
                    "semflow_research.public"
                ):
                    violations.append((str(path), node.lineno, module))
    assert violations == []


def test_platform_bridge_does_not_execute_another_algorithm():
    """Guard direct model/scanner/graph execution; projections/codecs stay here."""
    forbidden_imports = (
        "langgraph",
        "openai",
        "haystack",
        "subprocess",
        "app.workflows",
        "app.adapters.ai.provider",
        "app.adapters.codeql.scanner",
        "app.adapters.retrieval.knowledge",
    )
    forbidden_calls = {
        "StateGraph",
        "OpenAI",
        "CompatibleModel",
        "CodeQLScanner",
        "KnowledgeRetriever",
        "generate",
        "invoke",
        "ainvoke",
        "compile_query",
        "run_query",
        "validate_fixtures",
        "create_database",
        "analyze",
    }
    violations = []
    for path in (SYSTEM / "backend/app/research_bridge").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            imports = (
                [item.name for item in node.names]
                if isinstance(node, ast.Import)
                else [node.module or ""]
                if isinstance(node, ast.ImportFrom)
                else []
            )
            for name in imports:
                if any(
                    name == prefix or name.startswith(prefix + ".")
                    for prefix in forbidden_imports
                ):
                    violations.append((path.name, node.lineno, name))
            if isinstance(node, ast.Call):
                name = (
                    node.func.id
                    if isinstance(node.func, ast.Name)
                    else node.func.attr
                    if isinstance(node.func, ast.Attribute)
                    else ""
                )
                if name in forbidden_calls:
                    violations.append((path.name, node.lineno, name))
    assert violations == []
