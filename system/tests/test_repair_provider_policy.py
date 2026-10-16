"""The actual provider freezes Repair3 progress policy, not just a benchmark override."""

import httpx
from app.adapters.ai.policy import policy_snapshot
from app.core.audit_config import audit_settings
from app.core.db import engine
from app.persistence.stage_models import StageRun
from app.persistence.stage_repository import StageRepository
from app.services.context_materials import frozen_call, semantic_policy
from pydantic import BaseModel
from sqlmodel import Session

from tests.test_model_provider import completion, configured


def test_actual_provider_expands_source_and_passes_old_twelve_call_cap(
    pipeline_context, monkeypatch
):
    monkeypatch.setattr(audit_settings, "AI_AUDIT_EXECUTION_MODE", "progress")
    provider = configured(
        monkeypatch,
        lambda _: httpx.Response(200, json=completion('{"value":"observed"}')),
    )
    with Session(engine) as db:
        stage = StageRun(
            audit_id=pipeline_context["run_id"], kind="repair", prompt_version="3"
        )
        db.add(stage)
        db.commit()
        db.refresh(stage)
        identity = str(stage.id)
    assert StageRepository().claim(identity)
    provider.bind_stage(identity, "3")
    policy = semantic_policy(provider.response_directory)
    assert policy["repair_context_max_chars"] == 80000
    assert policy["repair_call_limit"] > 12
    assert (
        provider.policy["max_calls"]
        == provider.policy["max_tokens"]
        == provider.policy["max_seconds"]
        == 0
    )

    class Output(BaseModel):
        value: str

    for index in range(14):
        payload = {
            "phase": "inspect_semantics",
            "index": index,
            "evidence": [
                {"kind": "code", "reference": {"file": "a.py"}, "content": "x" * 41000}
            ],
        }
        assert (
            frozen_call(
                provider,
                "repair",
                payload,
                Output,
                provider.response_directory / f"test-call-{index}",
            ).value
            == "observed"
        )
    assert provider.usage["calls"] == 14
    assert StageRepository().get(identity).usage["calls"] == 14
    # Operator changes do not retroactively expand this persisted stage.
    monkeypatch.setattr(audit_settings, "SEMANTIC_REPAIR_MAX_CONTEXT_CHARS", 160000)
    provider.bind_stage(identity, "3")
    assert provider.policy["semantic_policy"]["repair_context_max_chars"] == 80000


def test_explicit_bounded_execution_preserves_operator_limits(monkeypatch):
    monkeypatch.setattr(audit_settings, "AI_AUDIT_EXECUTION_MODE", "bounded")
    monkeypatch.setattr(audit_settings, "AI_STAGE_MAX_CALLS", 17)
    assert policy_snapshot("repair")["max_calls"] == 17


def test_existing_frozen_repair3_stage_does_not_inherit_new_ceiling(
    pipeline_context, monkeypatch
):
    provider = configured(
        monkeypatch,
        lambda _: httpx.Response(200, json=completion('{"value":"observed"}')),
    )
    old = {"context_chars": 40000, "tool_limit": 8, "repair_attempts": 3}
    with Session(engine) as db:
        stage = StageRun(
            audit_id=pipeline_context["run_id"],
            kind="repair",
            prompt_version="3",
            model_config_snapshot={**policy_snapshot("repair"), "semantic_policy": old},
        )
        db.add(stage)
        db.commit()
        db.refresh(stage)
        identity = str(stage.id)
    provider.bind_stage(identity, "3")
    assert provider.policy["semantic_policy"] == old
    assert semantic_policy(provider.response_directory) == old
