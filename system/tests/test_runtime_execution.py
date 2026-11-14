"""Real graph/persistence lifecycle tests; scripted models do not measure quality."""

from uuid import UUID, uuid4

import pytest
from app.core.db import engine
from app.domain.audit import AuditError
from app.jobs.stages import execute_stage
from app.persistence.stage_models import Candidate, Evidence
from app.persistence.stage_repository import StageRepository
from app.runtime.checkpoints import stage_checkpoints
from app.runtime.stages import run_stage
from app.services.stage_actions import approve_stage, cancel_stage, retry_stage
from app.services.stage_lifecycle import create_stage_run
from pydantic import ValidationError
from sqlmodel import Session, select


class EvidenceModel:
    model = "scripted-runtime-test"
    invented = False

    def __init__(self):
        self.usage = {"calls": 0, "input_tokens": 0, "output_tokens": 0}

    def generate(self, purpose, payload, schema):
        self.usage["calls"] += 1
        return schema.model_validate(
            {
                "action": "final",
                "findings": [
                    {
                        "candidate_id": payload["targets"][0]["candidate_id"],
                        "title": "Untrusted dynamic execution",
                        "description": "The synthetic input reaches eval without a protection boundary.",
                        "assessment": "supported",
                        "evidence_ids": [str(uuid4())]
                        if self.invented
                        else [payload["evidence"][0]["id"]],
                    }
                ],
            }
        )


def create_review(context):
    with Session(engine) as session:
        return create_stage_run(
            session,
            context["run_id"],
            context["owner"],
            "review",
            {"discover": False},
            prompt_version="1",
            policy={"model": "frozen-test-model", "max_calls": 2},
        )


def setup_checkpoints():
    with stage_checkpoints() as saver:
        saver.setup()


def test_worker_and_direct_runtime_share_real_evidence_and_claim(
    pipeline_context, monkeypatch
):
    import app.jobs.stages as tasks

    setup_checkpoints()
    ctx = pipeline_context
    provider = EvidenceModel()
    monkeypatch.setattr(tasks, "CompatibleModel", lambda: provider)
    first = create_review(ctx)
    execute_stage.run(str(first.id))
    assert StageRepository().get(str(first.id)).status == "completed"
    execute_stage.run(str(first.id))
    assert provider.usage["calls"] == 1
    second = create_review(ctx)
    assert (
        run_stage(str(second.id), provider_factory=lambda: provider).status
        == "completed"
    )
    with Session(engine) as session:
        candidates = session.exec(
            select(Candidate).where(Candidate.audit_id == ctx["run_id"])
        ).all()
        assert {row.stage_id for row in candidates} == {first.id, second.id}
        for candidate in candidates:
            assert (
                candidate.status == "pending"
            )  # model support is not human confirmation
            evidence = session.get(Evidence, UUID(candidate.evidence_ids[0]))
            assert evidence.stage_id == candidate.stage_id
            assert evidence.content == "value = eval(input())"
            assert evidence.snapshot_hash
    # CLI/service creation applies the same confirmed-target gate as HTTP.
    with Session(engine) as session, pytest.raises(AuditError, match="人工确认"):
        create_stage_run(
            session,
            ctx["run_id"],
            ctx["owner"],
            "repair",
            {"candidate_ids": [str(candidates[0].id)]},
        )
    with Session(engine) as session, pytest.raises(AuditError, match="不存在"):
        create_stage_run(session, ctx["run_id"], uuid4(), "review", {})


def test_failure_and_cancelled_retry_preserve_history_and_frozen_policy(
    pipeline_context,
):
    setup_checkpoints()
    provider = EvidenceModel()
    provider.invented = True
    stage = create_review(pipeline_context)
    failed = run_stage(str(stage.id), provider_factory=lambda: provider)
    assert failed.status == "failed" and "未取到" in failed.error
    assert failed.result["failure"]["code"] == "audit_error"
    with Session(engine) as session:
        candidates = session.exec(
            select(Candidate).where(Candidate.stage_id == stage.id)
        ).all()
        assert candidates and all(row.status == "pending" for row in candidates)
        retried = retry_stage(session, stage.id, pipeline_context["owner"])
        assert retried.id != stage.id and retried.prompt_version == "1"
        assert retried.model_config_snapshot == stage.model_config_snapshot
        assert retried.model_calls == [] and retried.usage == {}
        cancel_stage(session, retried.id, pipeline_context["owner"])
    run_stage(str(retried.id), provider_factory=lambda: provider)
    assert provider.usage["calls"] == 1
    assert StageRepository().get(str(retried.id)).status == "cancelled"
    assert StageRepository().get(str(stage.id)).status == "failed"


def test_shared_runtime_persistent_approval_does_not_repeat_generation(
    pipeline_context, monkeypatch
):
    import app.runtime.stages as runtime

    from tests.test_rule_graph import setup_service

    setup_checkpoints()
    service, provider = setup_service(pipeline_context, monkeypatch)
    original = service.validate

    def validate(state):
        service.repository.update(
            service.stage_id, status="completed", phase="fixture_test_complete"
        )
        return {"validated": True}

    # Generation and approval use the real rule graph; external tools were replaced
    # by the existing deterministic rule fixture, not by a success-only runner.
    monkeypatch.setattr(service, "validate", validate)
    service_type = lambda identifier, model: service
    from app.workflows.rules import build_rule_graph

    monkeypatch.setattr(
        runtime, "stage_components", lambda kind: (service_type, build_rule_graph)
    )
    stage = run_stage(service.stage_id, provider_factory=lambda: provider)
    assert stage.status == "awaiting_confirmation" and provider.calls == 1
    with Session(engine) as session:
        with pytest.raises(ValidationError):
            approve_stage(session, stage.id, pipeline_context["owner"], "short")
        session.rollback()
        approved = approve_stage(
            session,
            stage.id,
            pipeline_context["owner"],
            "Reviewed positive and negative fixture source lines explicitly.",
        )
        assert approved.status == "queued"
    final = run_stage(service.stage_id, resume=True, provider_factory=lambda: provider)
    assert final.status == "completed" and provider.calls == 1
    monkeypatch.setattr(service, "validate", original)


def test_research_bridge_retains_failure_type_for_existing_recovery(
    pipeline_context, monkeypatch
):
    import app.runtime.stages as runtime
    from app.services.review import ReviewService
    from app.workflows.review import build_review_graph

    from scripts.benchmarks.formal_runtime import run_stage as research_run

    setup_checkpoints()
    provider = EvidenceModel()
    provider.invented = True
    monkeypatch.setattr(runtime, "CompatibleModel", lambda: provider)
    stage = create_review(pipeline_context)
    result = research_run(str(stage.id), ReviewService, build_review_graph)
    assert result["stage"]["status"] == "failed"
    assert result["stage"]["result"]["benchmark_error_type"] == "AuditError"
    assert result["candidates"] and result["candidates"][0]["status"] == "pending"
