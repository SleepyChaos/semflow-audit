"""Minimal repair CLI inputs and frozen synthetic discovery fixture."""

import json
import os
import subprocess
import sys
from pathlib import Path

from semflow_contracts.common import canonical_bytes
from semflow_contracts.discovery import CoverageReport
from semflow_contracts.results import Completeness, DiscoveryResult

from research.tests.native_cases import repair_spec
from research.tests.openhands_cases import openhands_spec
from research.tests.openhands_process_cases import resources
from research.tests.repair_cli_cases import SCRIPT


def published_discovery(case, spec):
    """Frozen synthetic discovery input, not a scanner/model quality claim."""
    coverage = case.artifacts.commit(
        canonical_bytes({"fixture": "one explicit source target"}),
        kind="coverage",
        schema_version="fixture/1",
    )
    body = DiscoveryResult(
        candidates=spec.inputs.targets.candidates,
        evidence=spec.inputs.targets.evidence,
        coverage=CoverageReport(
            status="full",
            scope_manifest=coverage,
            inspected_units=coverage,
            missing_units=coverage,
        ),
    )
    result = case.failed_result(
        execution_status="completed",
        failure=None,
        result=body,
        completeness=Completeness(status="full"),
    )
    assert case.ledger.claim(case.execution_id)
    case.ledger.publish(result, expected_revision=0)


def inputs(case, settings, tmp_path, monkeypatch, *, mode, engine="openhands"):
    spec = openhands_spec(case) if engine == "openhands" else repair_spec(case)
    published_discovery(case, spec)
    configured = (
        resources(tmp_path, settings, monkeypatch, mode=mode)
        if engine == "openhands"
        else settings
    )
    values = configured.model_dump(mode="json")
    for name in ("AI_BASE_URL", "AI_MODEL", "AI_API_KEY", "ARTIFACT_ROOT"):
        values.pop(name, None)
    resource = tmp_path / "resources.json"
    resource.write_text(
        json.dumps(
            {
                "profile_id": spec.policy.resource_profile,
                "settings": values,
                "model_endpoints": {
                    "scripted": {"base_url": "http://scripted.invalid"}
                },
            }
        )
    )
    options = tmp_path / "options.json"
    options.write_text(
        json.dumps(
            {
                "model": spec.model.model_dump(mode="json"),
                "policy": spec.policy.model_dump(mode="json"),
                **(
                    {"worker": spec.inputs.openhands.model_dump(mode="json")}
                    if engine == "openhands"
                    else {}
                ),
                "method_policy": spec.inputs.method_policy.model_dump(mode="json"),
                "validation_plan": spec.inputs.validation_plan.model_dump(mode="json"),
            }
        )
    )
    system = Path(__file__).resolve().parents[2]
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("AI_", "DATABASE_", "REDIS_", "PROJECT_"))
    }
    env["PYTHONPATH"] = os.pathsep.join(
        str(system / name / "src") for name in ("contracts", "research", "research_cli")
    )
    candidate_bundle = json.loads(
        case.artifacts.read(spec.inputs.targets.candidates.artifact)
    )
    arguments = [
        f"repair-{engine}",
        "--root",
        str(case.ledger.root),
        "--upstream-execution-id",
        str(case.execution_id),
        "--candidate-id",
        candidate_bundle["records"][0]["candidate_id"],
        "--writable",
        "app.py",
        "--max-changed-files",
        "1",
        "--options",
        str(options),
        "--resources",
        str(resource),
        "--dependency-lock",
        str(system / "uv.lock"),
        "--confirm",
        "--actor",
        "test-operator",
        "--reason",
        "Explicit operator selected the exact source evidence",
    ]
    return spec, env, arguments


def cli(env, arguments, tmp_path, *, timeout=30):
    return subprocess.run(
        [sys.executable, "-c", SCRIPT, *arguments],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
