"""Platform approval changes cannot silently renew a frozen rule execution."""

from datetime import timedelta
from uuid import UUID

import pytest
from app.main import app
from app.persistence.knowledge_models import RuleVersion
from app.persistence.stage_models import Decision, StageRun
from app.research_bridge.models import ResearchBinding
from app.research_bridge.requests import research_root
from app.runtime.stages import run_stage
from fastapi.testclient import TestClient
from semflow_research.public.runs import inspect
from sqlmodel import Session, select

from tests.research_rule_cases import setup_rule


@pytest.mark.parametrize(
    "changed",
    ["query", "modules", "dependencies", "fixtures", "latest_decision", "stage_inputs"],
)
def test_web_refuses_approval_of_changed_subject_or_human_input(
    bridge_case, scanner, monkeypatch, changed
):
    stage_id, phases, published = setup_rule(
        bridge_case, monkeypatch, with_holdout=True
    )
    stage = run_stage(stage_id)
    assert stage.status == "awaiting_confirmation", (stage.error, stage.result)
    previous = list(phases)
    deliveries = list(published)
    with Session(bridge_case[0]) as session:
        rule = session.get(RuleVersion, UUID(stage.result["rule_id"]))
        if changed == "query":
            rule.query += "\n// changed after pause"
        elif changed == "modules":
            rule.modules = {**rule.modules, "changed.qll": "import python"}
        elif changed == "dependencies":
            rule.dependencies = {"codeql/python-all": {"version": "changed"}}
        elif changed == "fixtures":
            rule.fixtures = {
                **rule.fixtures,
                "negative": {"files": {"changed.py": "eval(input())"}, "expected": []},
            }
        elif changed == "latest_decision":
            target = session.get(StageRun, UUID(stage_id)).inputs["candidate_id"]
            old = session.exec(
                select(Decision).where(Decision.candidate_id == UUID(target))
            ).one()
            session.add(
                Decision(
                    candidate_id=old.candidate_id,
                    actor_id=old.actor_id,
                    status="confirmed",
                    reason="A new confirmation must require a new execution",
                    evidence_ids=old.evidence_ids,
                    created_at=old.created_at + timedelta(seconds=1),
                )
            )
        else:
            current = session.get(StageRun, UUID(stage_id))
            current.inputs = {
                **current.inputs,
                "requirement": "Changed requirement after generation paused",
            }
            session.add(current)
        session.add(rule)
        session.commit()
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/rules/{stage.result['rule_id']}/approve-fixtures",
            json={"reason": "Reviewing an already stale subject must be rejected"},
        )
        assert response.status_code == 409, response.text
    assert phases == previous and published == deliveries
    with Session(bridge_case[0]) as session:
        current = session.get(StageRun, UUID(stage_id))
        assert current.status == "awaiting_confirmation"
        assert "research_control_command" not in current.result
        binding = session.exec(
            select(ResearchBinding).where(ResearchBinding.stage_id == current.id)
        ).one()
        assert (
            inspect(binding.execution_id, root=research_root()).execution_status
            == "awaiting_input"
        )


def test_rule_projection_recovers_committed_core_without_regeneration(
    bridge_case, scanner, monkeypatch
):
    stage_id, phases, _ = setup_rule(bridge_case, monkeypatch, with_holdout=True)
    from app.research_bridge import rule_runtime

    project = rule_runtime.project_rule
    attempts = []

    def interrupted(*args, **kwargs):
        attempts.append(True)
        raise RuntimeError(
            "Synthetic projection transaction interruption after scientific commit"
        )

    monkeypatch.setattr(rule_runtime, "project_rule", interrupted)
    failed = run_stage(stage_id)
    assert failed.status == "failed"
    with Session(bridge_case[0]) as session:
        binding = session.exec(
            select(ResearchBinding).where(ResearchBinding.stage_id == UUID(stage_id))
        ).one()
        waiting = inspect(binding.execution_id, root=research_root())
        assert waiting.execution_status == "awaiting_input" and binding.manifest is None
    previous = list(phases)
    monkeypatch.setattr(rule_runtime, "project_rule", project)
    recovered = rule_runtime.reconcile_bound(stage_id)
    assert recovered.status == "awaiting_confirmation"
    assert recovered.result["rule_id"]
    assert phases == previous and attempts == [True]
