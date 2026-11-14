"""New Web discovery tasks call the CLI's kernel; use only a disposable SQLite DB."""

from uuid import uuid4

from app.adapters.snapshot import snapshot_digest
from app.main import app
from app.persistence.audit_models import AuditRun
from app.persistence.stage_models import Candidate, Evidence, StageRun
from app.research_bridge.models import ResearchBinding
from app.research_bridge.requests import research_root
from app.runtime.stages import run_stage
from app.services.stage_lifecycle import create_stage_run
from fastapi.testclient import TestClient
from semflow_contracts.runs import validate_spec
from semflow_research.public.discovery import execute
from semflow_research.public.discovery_results import read_result
from semflow_research.public.runtime import ToolSettings, prepare
from sqlmodel import Session, select

from tests.research_bridge_cases import (
    ScoutModel,
    create_scout,
)


def test_web_scout_and_direct_sdk_share_the_same_kernel_and_api(bridge_case):
    db, _owner, audit_id, source = bridge_case
    stage = create_scout(bridge_case)
    model = ScoutModel()
    final = run_stage(str(stage.id), kernel_model_factory=lambda: model)
    assert final.status == "completed", final.error
    assert model.usage["calls"] == 1
    with Session(db) as session:
        binding = session.exec(
            select(ResearchBinding).where(ResearchBinding.stage_id == stage.id)
        ).one()
        assert binding.execution_id != stage.id
        assert (
            binding.request["source"]["tree_sha256"]
            != binding.legacy_source_digest
            == snapshot_digest(source)
        )
        rows = session.exec(select(Candidate)).all()
        evidence = session.exec(select(Evidence)).all()
        assert len(rows) == 1 and rows[0].status == "pending"
        assert evidence[0].digest and evidence[0].content == "value = eval(input())"
        assert rows[0].evidence_ids == [str(evidence[0].id)]
        assert (
            rows[0].evidence_ids[0] != final.result["research_receipt"]["execution_id"]
        )
        view = read_result(binding.execution_id, root=research_root())
        assert str(view.candidates[0].candidate_id) != str(rows[0].id)
        assert final.result["units"][0]["hypotheses"][0]["candidate_id"] == str(
            rows[0].id
        )
        spec = validate_spec({**binding.request, "execution_id": str(uuid4())})
        resources = ToolSettings.model_validate(binding.resources)
    # This is precisely the public route used by the independent CLI; no Web
    # service, ORM record or platform task is created by this second invocation.
    direct = execute(
        spec,
        prepare(spec, root=research_root(), settings=resources, model=ScoutModel()),
    )
    assert direct.execution_status == "completed", direct.failure
    observed = read_result(spec.execution_id, root=research_root())
    assert observed.candidates[0].description == view.candidates[0].description
    assert (
        observed.candidates[0].primary_location == view.candidates[0].primary_location
    )
    assert observed.trace.state["coverage"] == view.trace.state["coverage"]
    run_stage(str(stage.id), kernel_model_factory=lambda: model)
    assert model.usage["calls"] == 1
    with TestClient(app) as client:
        details = client.get(f"/api/v1/stages/{stage.id}")
        assert details.status_code == 200 and details.json()["status"] == "completed"
        materials = client.get(f"/api/v1/stages/{stage.id}/materials")
        assert materials.status_code == 200
        assert materials.json()["snapshot"] == binding.legacy_source_digest
        candidates = client.get(f"/api/v1/audits/{audit_id}/candidates")
        assert candidates.status_code == 200, candidates.text
        assert candidates.json()[0]["status"] == "pending"
        assert (
            client.get(f"/api/v1/stages/{stage.id}/evidence").json()[0]["content"]
            == "value = eval(input())"
        )


def test_old_unbound_stages_keep_their_executor_and_history(bridge_case, monkeypatch):
    db, _, audit_id, _ = bridge_case
    with Session(db) as session:
        old = StageRun(audit_id=audit_id, kind="scout", inputs={"historical": True})
        session.add(old)
        session.commit()
        session.refresh(old)
    calls = []

    def legacy(stage, provider, resume, service_type, graph_builder):
        calls.append(stage.id)
        from app.persistence.stage_repository import StageRepository

        StageRepository().update(
            str(stage.id), status="completed", result={"historical": "preserved"}
        )
        return {}

    monkeypatch.setattr("app.runtime.stages.invoke_graph", legacy)
    monkeypatch.setattr("app.runtime.stages.CompatibleModel", ScoutModel)
    final = run_stage(str(old.id))
    assert final.result == {"historical": "preserved"} and calls == [old.id]
    with Session(db) as session:
        assert (
            session.exec(
                select(ResearchBinding).where(ResearchBinding.stage_id == old.id)
            ).first()
            is None
        )


def test_committed_kernel_result_is_reprojected_without_another_model_call(
    bridge_case, monkeypatch
):
    import app.research_bridge.runtime as bridge

    db, _, _, _ = bridge_case
    stage, model = create_scout(bridge_case), ScoutModel()
    actual = bridge.project
    monkeypatch.setattr(
        bridge,
        "project",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError("simulated DB projection interruption")
        ),
    )
    first = run_stage(str(stage.id), kernel_model_factory=lambda: model)
    assert first.status == "failed" and model.usage["calls"] == 1
    with Session(db) as session:
        binding = session.exec(select(ResearchBinding)).one()
        assert binding.manifest is None
        assert not session.exec(select(Candidate)).all()
    monkeypatch.setattr(bridge, "project", actual)
    final = run_stage(str(stage.id), kernel_model_factory=lambda: model)
    assert final.status == "completed" and model.usage["calls"] == 1
    with Session(db) as session:
        assert len(session.exec(select(Candidate)).all()) == 1
        assert session.exec(select(ResearchBinding)).one().manifest is not None


def test_platform_cancellation_reaches_kernel_without_legacy_service(bridge_case):
    db, owner, _, _ = bridge_case
    stage = create_scout(bridge_case)

    class CancellingModel(ScoutModel):
        def generate(self, purpose, payload, schema):
            from app.services.stage_actions import cancel_stage

            with Session(db) as session:
                cancel_stage(session, stage.id, owner)
            return super().generate(purpose, payload, schema)

    final = run_stage(str(stage.id), kernel_model_factory=CancellingModel)
    assert final.status == "cancelled"
    with Session(db) as session:
        binding = session.exec(select(ResearchBinding)).one()
        from semflow_research.public.runs import inspect

        result = inspect(binding.execution_id, root=research_root())
        assert result.execution_status == "cancelled"
        assert result.failure.code == "cancelled"


def test_default_scout_mapping_preserves_every_native_control(bridge_case):
    from app.research_bridge.requests import freeze_stage

    db, owner, audit_id, _ = bridge_case
    with Session(db) as session:
        stage = create_stage_run(
            session,
            audit_id,
            owner,
            "scout",
            {
                "scheduling_profile": "runtime_first",
                "inspection_paths": ["app.py"],
                "max_units": 0,
                "include_third_party": True,
                "window_lines": 75,
                "max_context_chars": 24000,
                "steps_per_unit": 2,
            },
        )
        binding = session.exec(
            select(ResearchBinding).where(ResearchBinding.stage_id == stage.id)
        ).one()
        spec, settings = freeze_stage(binding, stage, session.get(AuditRun, audit_id))
        context = prepare(
            spec, root=research_root(), settings=settings, model=ScoutModel()
        )
        assert context.spec.implementation.method_version == stage.prompt_version == "7"
        assert context.execution_records.get(spec.execution_id).inputs == stage.inputs
        assert spec.model.output_tokens == max(
            6000, stage.model_config_snapshot["budgets"]["scout"]
        )
        assert (
            spec.policy.max_no_progress
            == stage.model_config_snapshot["max_no_progress"]
        )
        assert spec.inputs.window_policy.max_windows == 0
        assert spec.inputs.inspection_paths == ("app.py",)


def test_current_scout_method_keeps_grounded_findings_and_unknown_task_premises(
    bridge_case,
):
    from semflow_contracts.modelio.scouting import ScoutResponse

    class CurrentScoutModel(ScoutModel):
        def generate(self, purpose, payload, schema):
            body = (
                super()
                .generate(purpose, payload, ScoutResponse)
                .model_dump(mode="json")
            )
            body["findings"][0].update(
                security_property="input_injection", operation_quote="eval(input())"
            )
            body["task_checks"] = [
                {
                    "task_id": task["id"],
                    "status": "unknown",
                    "conclusion": "unknown",
                    "reason": "The source was read but the caller trust boundary remains unknown",
                    "evidence_ids": [],
                }
                for task in payload["inspection_tasks"]
            ]
            body["route_checks"] = []
            return schema.model_validate(body)

    db, owner, audit_id, _ = bridge_case
    with Session(db) as session:
        stage = create_stage_run(
            session, audit_id, owner, "scout", {"max_units": 1, "steps_per_unit": 1}
        )
    final = run_stage(str(stage.id), kernel_model_factory=CurrentScoutModel)
    assert final.status == "completed", final.error
    with Session(db) as session:
        candidates = session.exec(select(Candidate)).all()
        assert len(candidates) == 1
        assert candidates[0].status == "pending"
        assert final.result["units"][0]["task_checks"]
        assert all(
            check["status"] == "unknown"
            for check in final.result["units"][0]["task_checks"]
        )
        assert final.result["units"][0]["hypotheses"][0]["missing_premises"]


def test_bound_worker_never_injects_the_legacy_platform_model(bridge_case, monkeypatch):
    from app.jobs.stages import execute_stage
    from app.persistence.stage_repository import StageRepository
    from app.research_bridge import runtime

    stage = create_scout(bridge_case)

    def reject_legacy():
        raise AssertionError("Legacy provider must not enter the research kernel")

    monkeypatch.setattr("app.jobs.stages.CompatibleModel", reject_legacy)

    def check_dispatch(identifier, *, model):
        assert model is None  # Kernel creates its own frozen model adapter.
        StageRepository().update(identifier, status="completed")

    monkeypatch.setattr(runtime, "execute_bound", check_dispatch)
    execute_stage.run(str(stage.id))
    assert StageRepository().get(str(stage.id)).status == "completed"
