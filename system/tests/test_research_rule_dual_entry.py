"""One frozen scientific request enters actual Web worker and platform-free CLI."""

import json
import os
import shutil
from pathlib import Path
from uuid import UUID

from app.main import app
from app.persistence.stage_models import StageRun
from app.research_bridge.models import ResearchBinding
from app.research_bridge.requests import research_root
from app.runtime.stages import run_stage
from fastapi.testclient import TestClient
from semflow_research.public.runs import inspect
from sqlmodel import Session, select

from research.tests.rule_cli_cases import cli
from tests.research_rule_cases import setup_rule


def test_frozen_rule_request_has_same_web_and_fresh_cli_meaning(
    bridge_case, scanner, monkeypatch, tmp_path
):
    stage_id, phases, _ = setup_rule(bridge_case, monkeypatch, with_holdout=True)
    waiting_stage = run_stage(stage_id)
    assert waiting_stage.status == "awaiting_confirmation", (
        waiting_stage.error,
        waiting_stage.result,
    )
    with Session(bridge_case[0]) as session:
        binding = session.exec(
            select(ResearchBinding).where(ResearchBinding.stage_id == UUID(stage_id))
        ).one()
        request, resources, execution_id = (
            binding.request,
            binding.resources,
            binding.execution_id,
        )
    web_root = research_root()
    waiting = inspect(execution_id, root=web_root)
    cli_root = tmp_path / "independent-cli"
    shutil.copytree(web_root / "artifacts", cli_root / "artifacts")
    spec_path = tmp_path / "frozen-rule.json"
    spec_path.write_text(json.dumps(request))
    for key in ("AI_BASE_URL", "AI_MODEL", "AI_API_KEY", "ARTIFACT_ROOT"):
        resources.pop(key, None)
    resources_path = tmp_path / "rule-resources.json"
    resources_path.write_text(
        json.dumps(
            {
                "profile_id": request["policy"]["resource_profile"],
                "settings": resources,
                "model_endpoints": {
                    request["model"]["endpoint_profile"]: {
                        "base_url": "http://scripted.invalid/v1",
                        "api_key_env": "SEMFLOW_RULE_CLI_TEST_KEY",
                    }
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
    env.update(
        PYTHONPATH=os.pathsep.join(
            str(system / name)
            for name in (
                "contracts/src",
                "research/src",
                "research_cli/src",
                "research/tests",
            )
        ),
        SEMFLOW_RULE_CLI_TEST_KEY="explicit-synthetic-test-credential",
        SEMFLOW_RULE_CLI_PHASES=str(tmp_path / "cli-phases.json"),
        SEMFLOW_RULE_CLI_REPLAY="1",
    )
    root_args = ["--root", str(cli_root)]
    generated, cli_phases = cli(
        env,
        [
            "run",
            *root_args,
            "--spec",
            str(spec_path),
            "--resources",
            str(resources_path),
        ],
        tmp_path,
    )
    assert generated.returncode == 3, generated.stderr
    local_waiting = json.loads(generated.stdout)
    assert (
        cli_phases
        == phases
        == [
            "inspect_semantics",
            "generate_rule",
            "fixture_validation",
            "project_replay",
        ]
    )
    assert local_waiting["input_digest"] == waiting.input_digest
    rule_id = waiting_stage.result["rule_id"]
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/rules/{rule_id}/approve-fixtures",
            json={
                "reason": "Reviewed the exact frozen samples in this paired entry test"
            },
        )
        assert response.status_code == 200, response.text
    final_stage = run_stage(stage_id, resume=True)
    assert final_stage.status == "completed", (final_stage.error, final_stage.result)
    web_final = inspect(execution_id, root=web_root).model_dump(mode="json")
    decision, decision_phases = cli(
        env,
        [
            "decide",
            *root_args,
            "--execution-id",
            str(execution_id),
            "--actor",
            "test-operator",
            "--reason",
            "Reviewed exact CLI copies of these frozen query and samples",
        ],
        tmp_path,
    )
    assert decision.returncode == 0, decision.stderr
    assert decision_phases == []
    command = json.loads(decision.stdout)
    resumed, cli_phases = cli(
        env,
        [
            "resume",
            *root_args,
            "--decision-file",
            command["decision_file"],
            "--resources",
            str(resources_path),
        ],
        tmp_path,
    )
    assert resumed.returncode == 0, resumed.stderr
    local_final = json.loads(resumed.stdout)
    assert cli_phases == ["fixture_validation", "fixture_validation"]
    assert (
        local_final["execution_status"] == web_final["execution_status"] == "completed"
    )
    assert local_final["usage"]["calls"] == web_final["usage"]["calls"] == 2
    a, b = local_final["result"], web_final["result"]
    assert (
        a["outcome"] == b["outcome"] == "draft"
    )  # Human root confirmation remains platform-owned.
    assert a["purpose"] == b["purpose"] == "vulnerability_detector"
    assert a["rule"]["query_hash"] == b["rule"]["query_hash"]
    assert a["fixtures"]["sha256"] == b["fixtures"]["sha256"]
    assert a["rule"]["dependencies"]["sha256"] == b["rule"]["dependencies"]["sha256"]
    assert a["retrieval_trace"]["sha256"] == b["retrieval_trace"]["sha256"]
    for name in ("technical_validation", "independent_validation", "project_replay"):
        assert a[name]["status"] == b[name]["status"]
    assert a["project_replay"]["status"] == "inconclusive"
    with Session(bridge_case[0]) as session:
        assert session.get(StageRun, UUID(stage_id)).status == "completed"
