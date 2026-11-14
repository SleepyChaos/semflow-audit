"""Native repair bridge freezes human confirmed platform targets into typed inputs."""

from uuid import uuid4

from app.persistence.audit_models import AuditRun
from app.persistence.stage_models import StageRun
from app.research_bridge.models import ResearchBinding
from app.research_bridge.repair_requests import freeze_repair
from sqlmodel import Session, select

from tests.research_repair_cases import create_confirmed_repair


def test_native_repair_bridge_preserves_human_decision_and_scope(bridge_case, scanner):
    from app.core.audit_config import audit_settings
    from semflow_research.public.runtime import ToolSettings

    identifier = create_confirmed_repair(bridge_case)
    with Session(bridge_case[0]) as session:
        stage = session.get(StageRun, identifier)
        binding = session.exec(
            select(ResearchBinding).where(ResearchBinding.stage_id == identifier)
        ).one()
        spec = freeze_repair(
            binding, stage, session.get(AuditRun, stage.audit_id), session
        )
        session.add(binding)
        session.commit()  # Exercise real JSON serialization, not an in-memory dict.
        session.refresh(binding)
        assert spec.module == "repair" and spec.operation == "generate"
        assert spec.inputs.patch_scope.writable_paths == ("app.py",)
        assert spec.inputs.targets.decisions.artifact.kind == "decision_bundle"
        assert (
            spec.inputs.targets.candidates.artifact.owner_execution_id
            != binding.execution_id
        )
        assert spec.policy.decision_policy == "human_only"
        assert "AI_API_KEY" not in binding.resources
        assert isinstance(binding.resources["ARTIFACT_ROOT"], str)
        assert (
            ToolSettings.model_validate(binding.resources).model_dump(mode="json")
            == binding.resources
        )
        semantic = stage.model_config_snapshot["semantic_policy"]
        assert spec.inputs.method_policy.max_candidates == semantic["repair_attempts"]
        assert (
            spec.inputs.method_policy.model_call_limit == semantic["repair_call_limit"]
        )
        assert (
            spec.inputs.method_policy.inspection_limits.initial_source_steps
            == semantic["initial_source_tool_limit"]
        )
        assert (
            spec.model.output_tokens == stage.model_config_snapshot["budgets"]["repair"]
        )
        assert spec.policy.mode == audit_settings.AI_AUDIT_EXECUTION_MODE


def test_real_native_bridge_runs_graph_projects_and_serves_old_api(
    bridge_case, scanner, repair_model, syntax
):
    from app.main import app
    from app.persistence.stage_models import RepairRecord
    from app.runtime.stages import run_stage
    from fastapi.testclient import TestClient

    identifier = create_confirmed_repair(bridge_case)
    stage = run_stage(str(identifier))
    assert stage.status == "completed", (stage.error, stage.result)
    assert repair_model == [
        "inspect_semantics",
        "propose_patch",
        "assess_patch_contract",
    ]
    assert syntax == ["value = int(input())\n"]
    with Session(bridge_case[0]) as session:
        record = session.exec(
            select(RepairRecord).where(RepairRecord.stage_id == identifier)
        ).one()
        record_id = record.id
        assert record.status == "checks_passed"
    with TestClient(app) as client:
        response = client.get(f"/api/v1/repairs/{record_id}/diff")
        assert response.status_code == 200, response.text
        assert "+value = int(input())" in response.text


def test_new_bound_repair_worker_does_not_fall_back_to_legacy_provider(
    bridge_case, monkeypatch
):
    from app.jobs.stages import execute_stage
    from app.persistence.stage_models import StageRun
    from app.persistence.stage_repository import StageRepository
    from app.research_bridge import repair_runtime

    db, _owner, audit_id, _ = bridge_case
    with Session(db) as session:
        stage = StageRun(
            audit_id=audit_id,
            kind="repair",
            status="queued",
            phase="queued",
            inputs={"engine": "native", "candidate_ids": [str(uuid4())]},
        )
        session.add(stage)
        session.commit()
        session.refresh(stage)
        stage_id = stage.id
        session.add(ResearchBinding(stage_id=stage.id))
        session.commit()
    monkeypatch.setattr(
        "app.jobs.stages.CompatibleModel",
        lambda: (_ for _ in ()).throw(AssertionError("legacy provider")),
    )

    def worker(identifier, *, model):
        assert model is None
        StageRepository().update(
            identifier, status="completed", phase="repair_result_ready"
        )

    monkeypatch.setattr(repair_runtime, "execute_bound", worker)
    execute_stage.run(str(stage_id))
    assert StageRepository().get(str(stage_id)).phase == "repair_result_ready"
