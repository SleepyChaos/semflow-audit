"""API selects OpenHands, while platform still replays and reviews its candidate."""

import ast

from app.contracts.stages import RepairResponse
from app.services.context_materials import save_json

from tests.test_semantic_development import InspectModel, ready, repair_service


def test_api_engine_dispatch_keeps_independent_platform_validation(
    pipeline_context, monkeypatch
):
    from app.core.audit_config import audit_settings
    from app.jobs.stages import execute_stage
    from app.persistence.stage_repository import StageRepository
    from app.services import repair as native
    from app.services import repair_openhands as adapter
    from app.services.repair import RepairService
    from app.workflows.repair import build_repair_graph

    assessments = []

    def respond(payload):
        if payload["phase"] == "inspect_semantics":
            return ready(payload)
        assert payload["phase"] == "assess_patch_contract", (
            "Native generator must not produce this candidate"
        )
        assessments.append(payload)
        return {
            "constraints": [
                {
                    "fact_index": i,
                    "status": "consistent",
                    "explanation": "Numeric conversion preserves the synthetic fixture behavior",
                    "evidence_ids": [payload["evidence"][0]["id"]],
                }
                for i in payload["required_fact_indices"]
            ],
            "behavior_conflicts": [],
            "limitation": "Scripted review for platform wiring; not real model quality evidence",
        }

    initial = repair_service(pipeline_context, InspectModel(respond))
    initial.repository.update(initial.stage_id, status="cancelled")
    monkeypatch.setattr(execute_stage, "delay", lambda *_: None)
    response = pipeline_context["client"].post(
        f"/api/v1/audits/{pipeline_context['run_id']}/repair",
        json={**initial.inputs.model_dump(mode="json"), "engine": "openhands"},
    )
    assert response.status_code == 201
    stage = response.json()
    assert stage["inputs"]["engine"] == "openhands"
    assert StageRepository().claim(stage["id"])
    monkeypatch.setattr(audit_settings, "OPENHANDS_IMAGE", "test-only")
    monkeypatch.setattr(adapter, "resolve_image", lambda _: "sha256:test-only")
    observed = []

    def external(source, allowed, directory, config, prompt, **kwargs):
        assert allowed == ["app.py"] and "authorized_files" in prompt
        assert (source / "app.py").read_text() == "value = eval(input())\n"
        observed.append(str(directory))
        proposal = RepairResponse.model_validate(
            {
                "changes": [
                    {
                        "file": "app.py",
                        "old_text": "value = eval(input())\n",
                        "new_text": "value = int(input())\n",
                        "reason": "显式数值转换移除动态求值，同时保留正常整数输入",
                    }
                ],
                "summary": "通过隔离外部引擎生成测试候选，平台必须重新应用与验证",
            }
        )
        runtime = {
            "status": "completed",
            "metrics": {
                "token_usages": [{}],
                "accumulated_token_usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 20,
                },
            },
        }
        save_json(directory / "runtime-result.json", runtime)
        return {"proposal": proposal.model_dump(mode="json"), "runtime": runtime}

    def syntax(workspace, *_):
        ast.parse((workspace / "app.py").read_text())
        return {"status": "passed", "output": "Actual isolated syntax parsed"}

    monkeypatch.setattr(adapter, "generate", external)
    monkeypatch.setattr(native, "validate_workspace", syntax)
    model = InspectModel(respond)
    service = RepairService(stage["id"], model)
    result = build_repair_graph(service).invoke({})
    assert result["passed"] and result["attempt"] == 1
    assert len(observed) == 1 and len(assessments) == 1
    assert (service.evidence.root / "app.py").read_text() == "value = eval(input())\n"
    assert (
        service.directory / "attempt-1/workspace/app.py"
    ).read_text() == "value = int(input())\n"
    final = StageRepository().get(stage["id"])
    assert final.result["repair_engine"] == "openhands"
    assert final.result["independent_validation"]
    assert final.usage["calls"] == model.usage["calls"] + 1
    assert final.usage["native"] == model.usage
