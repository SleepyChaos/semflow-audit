"""Web and a fresh independent CLI consume the same frozen OpenHands request."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from app.core.audit_config import audit_settings
from app.persistence.stage_models import RepairRecord
from app.research_bridge.models import ResearchBinding
from app.research_bridge.requests import research_root
from app.runtime.stages import run_stage
from semflow_research.public.runs import inspect
from sqlmodel import Session, select

from research.tests.openhands_process_cases import resources
from research.tests.openhands_sdk_cases import sdk_resources
from research.tests.repair_cli_cases import SCRIPT
from tests.research_repair_cases import create_confirmed_repair


@pytest.mark.parametrize(
    "mode",
    [
        "success",
        "failed",
        pytest.param(
            "real_sdk",
            marks=[
                pytest.mark.integration,
                pytest.mark.skipif(
                    os.environ.get("AUDIT_RUN_REAL_TOOLS") != "1",
                    reason="Explicit real SDK/Docker opt-in",
                ),
            ],
        ),
    ],
)
def test_web_and_cli_same_openhands_process_contract(
    bridge_case, scanner, repair_model, syntax, monkeypatch, tmp_path, mode
):
    configured = (
        sdk_resources(audit_settings, tmp_path)
        if mode == "real_sdk"
        else resources(tmp_path, audit_settings, monkeypatch, mode=mode)
    )
    if mode == "real_sdk":
        from semflow_research.adapters.repair.validator import validate_workspace

        monkeypatch.setattr(
            "semflow_research.repair.repair.validate_workspace", validate_workspace
        )
        monkeypatch.setattr(
            audit_settings, "VALIDATOR_PYTHON_IMAGE", configured.VALIDATOR_PYTHON_IMAGE
        )
    for field in ("OPENHANDS_PYTHON", "OPENHANDS_IMAGE", "OPENHANDS_RUNNER"):
        monkeypatch.setattr(audit_settings, field, getattr(configured, field))
    monkeypatch.setattr(audit_settings, "OPENHANDS_MAX_STEPS", 4)
    stage_id = create_confirmed_repair(bridge_case, engine="openhands")
    stage = run_stage(str(stage_id))
    assert stage.status == ("completed" if mode != "failed" else "failed"), stage.error
    with Session(bridge_case[0]) as session:
        binding = session.exec(
            select(ResearchBinding).where(ResearchBinding.stage_id == stage_id)
        ).one()
        request, resource_values = dict(binding.request), dict(binding.resources)
        web = inspect(binding.execution_id, root=research_root())
        assert web.execution_status == stage.status
        if mode != "failed":
            record = session.exec(
                select(RepairRecord).where(RepairRecord.stage_id == stage_id)
            ).one()
            assert record.status == "checks_passed"
            assert record.validation["attempts_ref"] == web.result.attempts.model_dump(
                mode="json"
            )
        else:
            assert stage.result["failure"]["detail"] == web.failure.detail.model_dump(
                mode="json"
            )
    cli_root = tmp_path / "independent-cli"
    shutil.copytree(research_root() / "artifacts", cli_root / "artifacts")
    request["execution_id"] = str(uuid4())
    spec_path = tmp_path / "frozen-web-input.json"
    spec_path.write_text(json.dumps(request))
    for field in (
        "ARTIFACT_ROOT",
        "AI_MODEL",
        "AI_BASE_URL",
        "AI_API_KEY",
        "OPENHANDS_BASE_URL",
    ):
        resource_values.pop(field, None)
    resource_path = tmp_path / "cli-resources.json"
    resource_path.write_text(
        json.dumps(
            {
                "profile_id": request["policy"]["resource_profile"],
                "settings": resource_values,
                "model_endpoints": {
                    "platform-frozen": {"base_url": audit_settings.AI_BASE_URL}
                },
            }
        )
    )
    system = Path(__file__).resolve().parents[1]
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("AI_", "DATABASE_", "REDIS_", "PROJECT_"))
    }
    environment["PYTHONPATH"] = os.pathsep.join(
        str(system / package / "src")
        for package in ("contracts", "research", "research_cli")
    )
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            SCRIPT.replace(
                "native.validate_workspace=syntax",
                "from semflow_research.adapters.repair.validator import validate_workspace\nnative.validate_workspace=validate_workspace",
            )
            if mode == "real_sdk"
            else SCRIPT,
            "run",
            "--spec",
            str(spec_path),
            "--resources",
            str(resource_path),
            "--root",
            str(cli_root),
        ],
        env=environment,
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert completed.returncode == (0 if mode != "failed" else 1), (
        completed.stdout,
        completed.stderr,
    )
    cli = json.loads(completed.stdout)
    assert cli["execution_status"] == web.execution_status
    assert cli["completeness"]["status"] == web.completeness.status
    assert cli["usage"]["calls"] == web.usage.calls
    assert [
        (entry["model"], entry["calls"], entry["input_tokens"], entry["output_tokens"])
        for entry in cli["usage"]["by_provider"]
    ] == [
        (entry.model, entry.calls, entry.input_tokens, entry.output_tokens)
        for entry in web.usage.by_provider
    ]
    if mode != "failed":
        assert cli["result"]["outcome"] == web.result.outcome
        assert cli["result"]["patch"]["sha256"] == web.result.patch.sha256
        assert (
            cli["result"]["patched_source"]["tree_sha256"]
            == web.result.patched_source.tree_sha256
        )
        assert [
            (check["kind"], check["status"]) for check in cli["result"]["checks"]
        ] == [(check.kind, check.status) for check in web.result.checks]
    else:
        assert (
            cli["result"] is None
            and cli["failure"]["code"] == web.failure.code == "tool_failed"
        )
    if mode == "real_sdk":
        destination = os.environ.get("SEMFLOW_RESEARCH_GATE_REPORT")
        if destination:
            target = Path(destination) / "dual-entry" / str(web.execution_id)
            shutil.copytree(research_root(), target / "web")
            shutil.copytree(cli_root, target / "cli")
            (target / "web-result.json").write_text(web.model_dump_json(indent=2))
            (target / "cli-result.json").write_text(completed.stdout)
        assert run_stage(str(stage_id)).status == stage.status
        return
    calls = (tmp_path / "docker.log").read_text()
    again = run_stage(str(stage_id))
    assert again.status == stage.status
    assert (tmp_path / "docker.log").read_text() == calls  # No worker on redelivery.
