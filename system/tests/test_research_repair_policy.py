"""Frozen method controls and historical dispatch remain distinct at the bridge."""

from app.persistence.stage_models import StageRun
from app.persistence.stage_repository import StageRepository
from app.research_bridge.models import ResearchBinding
from app.research_bridge.requests import research_root
from app.runtime.stages import run_stage
from semflow_research.public.runs import inspect
from sqlmodel import Session, select

from tests.research_repair_cases import create_confirmed_repair


def test_progress_preserves_unbounded_totals_and_independent_repair_call_cap(
    bridge_case, scanner, repair_model, syntax, monkeypatch
):
    from app.core.audit_config import audit_settings

    monkeypatch.setattr(audit_settings, "AI_AUDIT_EXECUTION_MODE", "progress")
    monkeypatch.setattr(audit_settings, "REPAIR_MODEL_CALL_LIMIT", 1)
    monkeypatch.setattr(audit_settings, "REPAIR_SOURCE_TOOL_LIMIT", 6)
    monkeypatch.setattr(audit_settings, "REPAIR_INITIAL_SOURCE_TOOL_LIMIT", 2)
    monkeypatch.setattr(audit_settings, "REPAIR_ATTEMPTS", 3)
    stage_id = create_confirmed_repair(bridge_case)
    stage = run_stage(str(stage_id))
    assert stage.status == "failed", stage.result
    with Session(bridge_case[0]) as session:
        binding = session.exec(
            select(ResearchBinding).where(ResearchBinding.stage_id == stage_id)
        ).one()
        policy = binding.request["policy"]
        method = binding.request["inputs"]["method_policy"]
        assert policy["mode"] == "progress"
        assert (policy["max_calls"], policy["max_tokens"], policy["max_seconds"]) == (
            None,
            None,
            None,
        )
        assert method["model_call_limit"] == 1 and method["max_candidates"] == 3
        assert method["inspection_limits"]["max_steps"] == 6
        assert method["inspection_limits"]["initial_source_steps"] == 2
        receipt = inspect(binding.execution_id, root=research_root())
    assert receipt.failure.code == "budget_exhausted"
    assert receipt.usage.calls == 1
    assert repair_model == ["inspect_semantics"] and not syntax


def test_unbound_historical_repair_keeps_selected_legacy_executor(
    bridge_case, monkeypatch
):
    from uuid import uuid4

    audit_id = bridge_case[2]
    with Session(bridge_case[0]) as session:
        stage = StageRun(
            audit_id=audit_id,
            kind="repair",
            prompt_version="4",
            inputs={"engine": "openhands"},
        )
        session.add(stage)
        session.commit()
        session.refresh(stage)
        stage_id = stage.id
    calls = []

    class LegacyService:
        def __init__(self, identifier, provider):
            calls.append((identifier, provider))

    class LegacyGraph:
        def invoke(self, inputs, config):
            assert inputs == {"stage_id": str(stage_id)}
            StageRepository().update(
                str(stage_id), status="completed", phase="legacy_preserved"
            )
            return {}

    def build(service):
        assert isinstance(service, LegacyService)
        return LegacyGraph()

    provider = uuid4()
    result = run_stage(
        str(stage_id),
        provider_factory=lambda: provider,
        service_type=LegacyService,
        graph_builder=build,
        kernel_model_factory=lambda: (_ for _ in ()).throw(
            AssertionError("must stay legacy")
        ),
    )
    assert result.status == "completed" and result.phase == "legacy_preserved"
    assert calls == [(str(stage_id), provider)]


def test_new_openhands_request_is_bound_and_missing_resources_fail_explicitly(
    bridge_case, scanner, monkeypatch
):
    from app.core.audit_config import audit_settings
    from app.research_bridge.models import ResearchBinding
    from app.runtime.stages import run_stage

    stage_id = create_confirmed_repair(bridge_case, engine="openhands")
    monkeypatch.setattr(audit_settings, "OPENHANDS_IMAGE", "")
    monkeypatch.setattr(audit_settings, "OPENHANDS_PYTHON", "")
    stage = run_stage(str(stage_id))
    assert stage.status == "failed"
    with Session(bridge_case[0]) as session:
        binding = session.exec(
            select(ResearchBinding).where(ResearchBinding.stage_id == stage_id)
        ).one()
        assert binding.request == {}
