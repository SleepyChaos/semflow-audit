"""Human decisions, approval and bounded research configuration at the CLI edge."""

import json
from uuid import UUID, uuid4

from app.adapters.ai.experiment_policy import frozen_policy
from app.cli.main import main
from app.contracts.experiments import ExperimentStage
from app.core.db import engine
from app.persistence.knowledge_models import RuleVersion
from app.persistence.stage_models import Candidate, Decision
from app.runtime.stages import run_stage
from app.workflows.rules import build_rule_graph
from sqlmodel import Session, select

from tests.test_experiment_cli import cli_context, plan_file, review_sample
from tests.test_rule_graph import setup_service
from tests.test_runtime_execution import setup_checkpoints


def test_cli_decisions_require_real_owned_evidence(
    pipeline_context, monkeypatch, capsys
):
    ctx = pipeline_context
    cli_context(ctx, monkeypatch)
    path = plan_file(ctx, [review_sample(ctx)])
    assert main(["run", "--config", str(path)]) == 0
    row = json.loads(capsys.readouterr().out)["runs"][0]["stages"][0]
    with Session(engine) as session:
        candidate = session.exec(
            select(Candidate).where(Candidate.stage_id == UUID(row["id"]))
        ).one()
        identifier, evidence_id = str(candidate.id), candidate.evidence_ids[0]
    args = [
        "decide",
        "--candidate-id",
        identifier,
        "--status",
        "confirmed",
        "--reason",
        "Explicit human review of the source input-to-eval path.",
    ]
    assert main([*args, "--evidence-id", str(uuid4())]) == 2
    assert json.loads(capsys.readouterr().err)["error"] == "invalid_input"
    with Session(engine) as session:
        assert session.get(Candidate, UUID(identifier)).status == "pending"
    assert main([*args, "--evidence-id", evidence_id]) == 0
    decision = json.loads(capsys.readouterr().out)
    assert decision["evidence_ids"] == [evidence_id]
    with Session(engine) as session:
        assert session.get(Candidate, UUID(identifier)).status == "confirmed"
        history = session.exec(
            select(Decision).where(Decision.candidate_id == UUID(identifier))
        ).all()
        assert len(history) == 1 and history[0].actor_id == ctx["owner"]


def test_cli_resume_requires_reason_and_keeps_persistent_generation(
    pipeline_context, monkeypatch, capsys
):
    import app.runtime.stages as runtime

    ctx = pipeline_context
    cli_context(ctx, monkeypatch)
    setup_checkpoints()
    service, provider = setup_service(ctx, monkeypatch)

    def factory(identifier, model):
        assert identifier == service.stage_id
        return service

    def validate(state):
        service.repository.update(service.stage_id, status="completed")
        return {"validated": True}

    monkeypatch.setattr(service, "validate", validate)
    monkeypatch.setattr(
        runtime, "stage_components", lambda kind: (factory, build_rule_graph)
    )
    monkeypatch.setattr(runtime, "CompatibleModel", lambda: provider)
    assert run_stage(service.stage_id).status == "awaiting_confirmation"
    assert main(["resume", "--run-id", service.stage_id, "--reason", "short"]) == 2
    capsys.readouterr()
    reason = "Manually checked the positive and negative fixture files and expected locations."
    assert main(["resume", "--run-id", service.stage_id, "--reason", reason]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "completed"
    assert provider.calls == 1
    with Session(engine) as session:
        rule = session.exec(
            select(RuleVersion).where(RuleVersion.stage_id == UUID(service.stage_id))
        ).one()
        assert rule.fixtures_approved and rule.fixture_approval_reason == reason
    assert main(["resume", "--run-id", service.stage_id, "--reason", reason]) == 2
    capsys.readouterr()
    assert provider.calls == 1


def test_rule_ablation_freezes_only_explicit_existing_switches():
    spec = ExperimentStage.model_validate(
        {
            "kind": "rule",
            "prompt_version": "8",
            "inputs": {"requirement": "Generate a Python eval vulnerability detector"},
            "rule_experiment": {
                "retrieval_mode": "bm25",
                "full_feedback": False,
                "collection_routing": False,
            },
            "budget": {"max_calls": 4, "max_tokens": 12000, "max_seconds": 90},
        }
    )
    policy = frozen_policy(spec)
    assert policy["rule_experiment"] == {
        "retrieval_mode": "bm25",
        "full_feedback": False,
        "collection_routing": False,
    }
    assert policy["max_calls"] == 4 and policy["execution_mode"] == "bounded"
    assert policy["prompt_snapshot"]["version"] == "8"
