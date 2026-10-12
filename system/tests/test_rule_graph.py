"""Graph lifecycle tests. Scripted candidates do not measure LLM quality."""

import json
from uuid import UUID, uuid4

import pytest
from app.core.db import engine
from app.domain.audit import AuditError
from app.persistence.knowledge_models import RuleVersion
from app.persistence.stage_repository import StageCancelled
from app.services.rules import RuleService
from app.workflows.rules import build_rule_graph
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from sqlmodel import Session, select

from tests.test_rule_synthesis import draft, make_stage


def setup_service(context, monkeypatch, *, fail=False, cancel=False):
    import app.services.rule_synthesis as synthesis

    identifier = uuid4()
    stage = make_stage(context, {"full_feedback": True, "execute_dev": True})

    class Provider:
        model = "fixture-only"

        def __init__(self):
            self.usage = {}
            self.calls = 0

        def generate(self, purpose, payload, schema):
            self.calls += 1
            result = draft(identifier)
            result.query = """/**
 * @id audit/graph-fixture
 * @name graph fixture
 * @description lifecycle fixture
 * @kind problem
 * @problem.severity warning
 * @precision low
 */
import python
from Call c select c, "candidate"
"""
            if cancel:
                service.repository.update(stage, status="cancelled")
            return result

    provider = Provider()
    service = RuleService(stage, provider)
    monkeypatch.setattr(
        service,
        "retrieve",
        lambda: {"knowledge": [{"id": str(identifier)}], "target": None},
    )
    monkeypatch.setattr(synthesis, "compile_query", lambda *args: None)
    monkeypatch.setattr(
        synthesis,
        "validate_fixtures",
        lambda *args: {"status": "failed" if fail else "passed", "tests": {}},
    )
    return service, provider


def timings(service):
    return [
        json.loads(p.read_text())
        for p in (service.directory / "node-timings").glob("*.json")
    ]


def test_failed_development_exhausts_two_attempts_without_approval(
    pipeline_context, monkeypatch
):
    service, provider = setup_service(pipeline_context, monkeypatch, fail=True)
    with pytest.raises(AuditError, match="两次"):
        build_rule_graph(service).invoke({"stage_id": service.stage_id})
    assert provider.calls == 2
    with Session(engine) as db:
        assert not db.exec(
            select(RuleVersion).where(RuleVersion.stage_id == service.stage.id)
        ).all()
    records = timings(service)
    assert not any(r["node"] == "approve_fixtures" for r in records)
    assert (
        sum(
            r.get("candidate_passed") is False and r["node"] == "execute_development"
            for r in records
        )
        == 2
    )
    assert all(r["seconds"] >= 0 and r["status"] != "running" for r in records)
    inputs = json.loads((service.directory / "draft-1/input.json").read_text())
    assert inputs["development_feedback"]["status"] == "failed"
    assert "independent_holdout" not in inputs


def test_cancelled_generation_cannot_enter_compilation(pipeline_context, monkeypatch):
    service, provider = setup_service(pipeline_context, monkeypatch, cancel=True)
    with pytest.raises(StageCancelled):
        build_rule_graph(service).invoke({"stage_id": service.stage_id})
    assert provider.calls == 1
    records = timings(service)
    assert any(r["status"] == "cancelled" for r in records)
    assert not any(r["node"] == "compile_draft" for r in records)


def test_checkpoint_and_approval_resume_do_not_repeat_generation(
    pipeline_context, monkeypatch
):
    service, provider = setup_service(pipeline_context, monkeypatch)
    validations = []
    monkeypatch.setattr(
        service,
        "validate",
        lambda state: validations.append(state["rule_id"]) or {"validated": True},
    )
    graph = build_rule_graph(service, InMemorySaver())
    config = {"configurable": {"thread_id": service.stage_id}}
    graph.invoke(
        {"stage_id": service.stage_id}, config, interrupt_before=["compile_draft"]
    )
    assert provider.calls == 1
    state = graph.get_state(config)
    assert state.next == ("compile_draft",)
    assert state.values["draft_path"] == "draft-0"
    assert "query" not in state.values
    paused = graph.invoke(None, config)
    assert paused["__interrupt__"]
    assert not validations
    with Session(engine) as db:
        rule = db.get(RuleVersion, UUID(paused["rule_id"]))
        rule.fixtures_approved = True
        db.add(rule)
        db.commit()
    result = graph.invoke(Command(resume={"approved": True}), config)
    assert result["validated"]
    assert provider.calls == 1
    assert validations == [paused["rule_id"]]
    # Simulate persistence replay after a DB commit and before its checkpoint.
    from app.services.rule_synthesis import RuleSynthesis

    assert RuleSynthesis(service).persist(result)["rule_id"] == paused["rule_id"]
    with Session(engine) as db:
        assert (
            len(
                db.exec(
                    select(RuleVersion).where(RuleVersion.stage_id == service.stage.id)
                ).all()
            )
            == 1
        )
    assert any(
        r["node"] == "approve_fixtures" and r["status"] == "interrupted"
        for r in timings(service)
    )


def test_replay_after_model_commit_reuses_candidate_and_rejects_changes(
    pipeline_context, monkeypatch
):
    from app.services.rule_synthesis import RuleSynthesis

    service, provider = setup_service(pipeline_context, monkeypatch)
    synthesis = RuleSynthesis(service)
    state = service.retrieve()
    saved = synthesis.propose(state)
    assert synthesis.propose(state) == saved
    assert provider.calls == 1
    candidate = service.directory / saved["draft_path"] / "candidate.json"
    content = candidate.read_text()
    candidate.write_text(content.replace("eval detector", "tampered"))
    with pytest.raises(AuditError, match="被修改"):
        synthesis.propose(state)
    with pytest.raises(AuditError, match="被修改"):
        synthesis.compile({**state, **saved})
    assert provider.calls == 1
