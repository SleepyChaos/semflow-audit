"""Fresh CLI suite/comparison input assembly and immutable identity enforcement."""

import json
from pathlib import Path
from uuid import UUID

import pytest
from semflow_contracts.errors import ResearchError
from semflow_research.public.runs import specification
from semflow_research.public.verification_requests import VerifyOptions, assemble_verify
from semflow_research.runtime.artifacts import LocalArtifacts

from research.tests.minimal_repair_cases import cli, inputs


def test_minimal_suite_and_comparison_use_exact_published_repair(
    research_case, settings, tmp_path, monkeypatch
):
    original, environment, arguments = inputs(
        research_case, settings, tmp_path, monkeypatch, mode="success", engine="native"
    )
    repaired = cli(environment, arguments, tmp_path)
    assert repaired.returncode == 0, repaired.stderr
    repair = json.loads(repaired.stdout)
    root = research_case.ledger.root
    option_path = tmp_path / "suite-options.json"
    option_path.write_text(
        json.dumps(
            {
                "model": original.model.model_dump(mode="json"),
                "policy": original.policy.model_dump(mode="json"),
            }
        )
    )
    requirements = tmp_path / "behavior.txt"
    requirements.write_text(
        "Reject expression input and preserve integer input exactly.\n"
    )

    def arg(name):
        return arguments[arguments.index(name) + 1]

    common = [
        "--root",
        str(root),
        "--resources",
        arg("--resources"),
        "--dependency-lock",
        arg("--dependency-lock"),
    ]
    built = cli(
        environment,
        [
            "repair-build-suite",
            *common,
            "--options",
            str(option_path),
            "--upstream-execution-id",
            str(research_case.execution_id),
            "--candidate-id",
            arg("--candidate-id"),
            "--confirm",
            "--actor",
            "suite-operator",
            "--reason",
            "Review the exact selected source evidence",
            "--requirements-file",
            str(requirements),
        ],
        tmp_path,
    )
    assert built.returncode == 0, built.stderr
    suite = json.loads(built.stdout)
    build_spec = specification(UUID(suite["execution_id"]), root=root)
    assert build_spec.source == original.source
    assert build_spec.inputs.targets.candidates.entity_ids == (
        UUID(arg("--candidate-id")),
    )
    assert (
        LocalArtifacts(root / "artifacts", build_spec.execution_id)
        .read(
            build_spec.inputs.requested_behavior,
        )
        .decode("utf-8")
        == requirements.read_text()
    )
    assert suite["result"]["review_required"] is True
    option_path.write_text(
        json.dumps(
            {
                "policy": original.policy.model_dump(mode="json"),
                "syntax": False,
                "project_tests": False,
                "rescan": False,
            }
        )
    )
    checked = cli(
        environment,
        [
            "repair-verify",
            *common,
            "--options",
            str(option_path),
            "--repair-execution-id",
            repair["execution_id"],
            "--suite-execution-id",
            suite["execution_id"],
        ],
        tmp_path,
    )
    assert checked.returncode == 0, checked.stderr
    result = json.loads(checked.stdout)
    request = specification(UUID(result["execution_id"]), root=root)
    assert request.inputs.patch.model_dump(mode="json") == repair["result"]["patch"]
    assert (
        request.inputs.patched_source.tree_sha256
        == repair["result"]["patched_source"]["tree_sha256"]
    )
    assert (
        request.inputs.suite.definition.sha256
        == suite["result"]["suite"]["definition"]["sha256"]
    )
    assert result["result"]["receipt"]["status"] == "passed"
    assert result["usage"]["calls"] == 0
    inspected = cli(
        environment,
        ["inspect", "--root", str(root), "--execution-id", result["execution_id"]],
        tmp_path,
    )
    assert inspected.returncode == 0 and json.loads(inspected.stdout) == result
    # Sender must not silently enable a current default scanner without a frozen baseline.
    with pytest.raises(ResearchError, match="baseline"):
        assemble_verify(
            root=root,
            repair_execution_id=UUID(repair["execution_id"]),
            suite_execution_id=UUID(suite["execution_id"]),
            options=VerifyOptions(policy=original.policy, rescan=True),
            dependency_lock=Path(arg("--dependency-lock")),
        )
