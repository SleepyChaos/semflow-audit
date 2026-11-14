"""Web and a fresh independent CLI consume the same frozen native request."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

from app.persistence.stage_models import RepairRecord
from app.research_bridge.models import ResearchBinding
from app.research_bridge.requests import research_root
from app.runtime.stages import run_stage
from semflow_research.public.runs import inspect
from sqlmodel import Session, select

from research.tests.repair_cli_cases import SCRIPT
from tests.research_repair_cases import create_confirmed_repair


def test_web_and_cli_same_native_process_contract(
    bridge_case, scanner, repair_model, syntax, tmp_path
):
    stage_id = create_confirmed_repair(bridge_case, engine="native")
    stage = run_stage(str(stage_id))
    assert stage.status == "completed", stage.error
    with Session(bridge_case[0]) as session:
        binding = session.exec(
            select(ResearchBinding).where(ResearchBinding.stage_id == stage_id)
        ).one()
        request, resource_values = dict(binding.request), dict(binding.resources)
        web = inspect(binding.execution_id, root=research_root())
        record = session.exec(
            select(RepairRecord).where(RepairRecord.stage_id == stage_id)
        ).one()
        assert record.status == "checks_passed"
    cli_root = tmp_path / "independent-cli"
    shutil.copytree(research_root() / "artifacts", cli_root / "artifacts")
    request["execution_id"] = str(uuid4())
    spec_path = tmp_path / "frozen-native-input.json"
    spec_path.write_text(json.dumps(request))
    for field in ("ARTIFACT_ROOT", "AI_MODEL", "AI_BASE_URL", "AI_API_KEY"):
        resource_values.pop(field, None)
    resource_path = tmp_path / "native-resources.json"
    resource_path.write_text(
        json.dumps(
            {
                "profile_id": request["policy"]["resource_profile"],
                "settings": resource_values,
                "model_endpoints": {
                    "platform-frozen": {"base_url": "http://scripted.invalid/v1"}
                },
            }
        )
    )
    system = Path(__file__).resolve().parents[1]
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("AI_", "DATABASE_", "REDIS_", "PROJECT_"))
    }
    env["PYTHONPATH"] = os.pathsep.join(
        str(system / package / "src")
        for package in ("contracts", "research", "research_cli")
    )
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            SCRIPT,
            "run",
            "--spec",
            str(spec_path),
            "--resources",
            str(resource_path),
            "--root",
            str(cli_root),
        ],
        env=env,
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, (completed.stdout, completed.stderr)
    cli = json.loads(completed.stdout)
    assert cli["execution_status"] == web.execution_status == "completed"
    assert cli["result"]["outcome"] == web.result.outcome == "checks_passed"
    assert cli["result"]["patch"]["sha256"] == web.result.patch.sha256
    assert (
        cli["result"]["patched_source"]["tree_sha256"]
        == web.result.patched_source.tree_sha256
    )
    assert [(check["kind"], check["status"]) for check in cli["result"]["checks"]] == [
        (check.kind, check.status) for check in web.result.checks
    ]
