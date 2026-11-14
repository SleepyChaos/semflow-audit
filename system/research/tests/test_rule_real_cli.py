"""Opt-in tiny real CodeQL gate; scripted model and operator, no quality claim."""

import json
import os
import shutil
from pathlib import Path
from uuid import UUID

import pytest
from semflow_research.public.runs import inspect

from research.tests.rule_cases import install_substitutes
from research.tests.rule_cli_cases import cli, inputs


@pytest.mark.integration
@pytest.mark.skipif(
    os.environ.get("AUDIT_RUN_REAL_TOOLS") != "1", reason="explicit local CodeQL opt-in"
)
def test_real_codeql_rule_cli_approves_and_checks_generated_and_independent_samples(
    research_case, settings, monkeypatch, tmp_path
):
    install_substitutes(
        monkeypatch, []
    )  # Only prepare the local mechanical options fixture.
    env, arguments, resource_path = inputs(
        research_case, settings, tmp_path, holdout=True
    )
    system = Path(__file__).resolve().parents[2]
    resources = json.loads(resource_path.read_bytes())
    resources["settings"].update(
        CODEQL_BIN=shutil.which("codeql"),
        CODEQL_PYTHON_BIN=shutil.which("python3.11"),
        CODEQL_PACK_PATH=str(system.parent / "artifacts/packs"),
        PYTHON_QUERY_PACK="codeql/python-queries@1.6.0",
        CODEQL_RAM=2048,
    )
    resource_path.write_text(json.dumps(resources))
    option_path = Path(arguments[arguments.index("--options") + 1])
    options = json.loads(option_path.read_bytes())
    options["policy"].update(max_seconds=1200, tool_timeout_seconds=240)
    option_path.write_text(json.dumps(options))
    documents = Path(arguments[arguments.index("--documents") + 1])
    body = json.loads(documents.read_bytes())
    for doc in body:
        doc["provenance"]["api_version"] = "4.0.10"
    documents.write_text(json.dumps(body))
    env["SEMFLOW_RULE_CLI_REAL_TOOLS"] = "1"
    generated, phases = cli(env, arguments, tmp_path, timeout=900)
    assert generated.returncode == 3, generated.stderr + generated.stdout
    waiting = json.loads(generated.stdout)
    assert phases == ["inspect_semantics", "generate_rule"]
    root_args = ["--root", str(research_case.ledger.root)]
    decision, _ = cli(
        env,
        [
            "decide",
            *root_args,
            "--execution-id",
            waiting["execution_id"],
            "--actor",
            "explicit-test-operator",
            "--reason",
            "Reviewed exact scripted eval anchor and generated positive and negative samples",
        ],
        tmp_path,
    )
    assert decision.returncode == 0, decision.stderr
    resumed, phases = cli(
        env,
        [
            "resume",
            *root_args,
            "--decision-file",
            json.loads(decision.stdout)["decision_file"],
            "--resources",
            str(resource_path),
        ],
        tmp_path,
        timeout=900,
    )
    assert resumed.returncode == 0, resumed.stderr + resumed.stdout
    assert (
        phases == []
    )  # Native compile/database/query tools execute without model regeneration.
    final = json.loads(resumed.stdout)
    assert final["result"]["outcome"] == "checks_passed"
    assert final["result"]["rule"] == waiting["result"]["rule"]
    for field in ("technical_validation", "independent_validation"):
        assert final["result"][field]["status"] == "passed"
    root = research_case.ledger.root
    inspected = inspect(UUID(final["execution_id"]), root=root)
    assert inspected.usage.calls == 2
    raw = final["result"]["independent_validation"]["raw_output"]
    evidence = json.loads(
        (root / "artifacts" / raw["owner_execution_id"] / raw["path"]).read_bytes()
    )
    assert evidence["codeql_version"] != "scripted-codeql"
    assert len(evidence["tests"]["positive"]["actual"]) == 3
    assert evidence["tests"]["negative"]["actual"] == []
    report = os.environ.get("SEMFLOW_RESEARCH_RULE_GATE_REPORT")
    if report:
        destination = Path(report) / final["execution_id"]
        destination.mkdir(parents=True)
        shutil.copytree(root, destination / "research")
        (destination / "result.json").write_text(json.dumps(final, indent=2))
        (destination / "scope.json").write_text(
            json.dumps(
                {
                    "scope": "Tiny existing eval anchor micro-fixtures; scripted model and human operator",
                    "codeql_version": evidence["codeql_version"],
                    "model_quality_evaluated": False,
                    "project_replay_requested": False,
                    "input_digest": final["input_digest"],
                },
                indent=2,
            )
        )
