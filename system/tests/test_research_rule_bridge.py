"""Real Web/worker/public rule graph with only external tool/model substitutes."""

from uuid import UUID

import pytest
from app.main import app
from app.persistence.knowledge_models import RuleVersion
from app.runtime.stages import run_stage
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from tests.research_rule_cases import setup_rule


def test_rule_retrieval_failure_remains_failed_without_legacy_fallback(
    bridge_case, scanner, monkeypatch
):
    stage_id, phases, _ = setup_rule(bridge_case, monkeypatch, missing_corpus=True)
    stage = run_stage(stage_id)
    assert stage.status == "failed", (stage.error, stage.result)
    assert phases == ["inspect_semantics"]
    with Session(bridge_case[0]) as session:
        assert (
            session.exec(
                select(RuleVersion).where(RuleVersion.stage_id == UUID(stage_id))
            ).first()
            is None
        )


@pytest.mark.parametrize("with_holdout", [False, True])
def test_rule_web_generation_approval_replay_and_publication(
    bridge_case, scanner, monkeypatch, with_holdout
):
    stage_id, phases, published = setup_rule(
        bridge_case, monkeypatch, with_holdout=with_holdout
    )
    stage = run_stage(stage_id)
    assert stage.status == "awaiting_confirmation", (stage.error, stage.result)
    assert phases == [
        "inspect_semantics",
        "generate_rule",
        "fixture_validation",
        "project_replay",
    ]
    with TestClient(app) as client:
        rows = client.get("/api/v1/rules/").json()
        rule = next(row for row in rows if row["stage_id"] == stage_id)
        identifier = rule["id"]
        assert rule["status"] == "draft" and rule["fixtures_approved"] is False
        assert "from Call" in client.get(f"/api/v1/rules/{identifier}/query").text
        assert client.post(f"/api/v1/rules/{identifier}/publish").status_code == 409
        approved = client.post(
            f"/api/v1/rules/{identifier}/approve-fixtures",
            json={
                "reason": "Reviewed the exact query, dependencies and positive and negative samples"
            },
        )
        assert approved.status_code == 200, approved.text
        assert published[-1] == (stage_id, True)
    resumed = run_stage(stage_id, resume=True)
    assert resumed.status == "completed", (resumed.error, resumed.result)
    assert phases.count("generate_rule") == 1 and phases.count("project_replay") == 1
    with TestClient(app) as client:
        rule = client.get(f"/api/v1/rules/{identifier}").json()
        assert rule["fixtures_approved"] is True
        assert rule["validation"]["independent_holdout"]["status"] == (
            "passed" if with_holdout else "not_evaluated"
        )
        replay = rule["validation"]["project_replay"]
        assert replay["status"] == "candidate_match_needs_confirmation"
        assert client.post(f"/api/v1/rules/{identifier}/publish").status_code == 409
        confirmed = client.post(
            f"/api/v1/rules/{identifier}/confirm-project-match",
            json={
                "finding_id": replay["matched_ids"][0],
                "reason": "Reviewed the source to sink path and confirmed it is the exact target root cause",
            },
        )
        assert confirmed.status_code == 200, confirmed.text
        outcome = client.post(f"/api/v1/rules/{identifier}/publish")
        assert outcome.status_code == (200 if with_holdout else 409), outcome.text
    previous = list(phases)
    assert run_stage(stage_id, resume=True).status == "completed"
    assert phases == previous


def test_existing_project_match_route_is_the_platform_validation_acceptance_gate(
    bridge_case, scanner, monkeypatch
):
    """The existing Web operation exposes the completed research validation receipts."""
    stage_id, phases, _ = setup_rule(bridge_case, monkeypatch, with_holdout=True)
    stage = run_stage(stage_id)
    assert stage.status == "awaiting_confirmation"
    with TestClient(app) as client:
        rule = next(
            row
            for row in client.get("/api/v1/rules/").json()
            if row["stage_id"] == stage_id
        )
        approved = client.post(
            f"/api/v1/rules/{rule['id']}/approve-fixtures",
            json={"reason": "Reviewed the exact frozen validation inputs"},
        )
        assert approved.status_code == 200
    final = run_stage(stage_id, resume=True)
    assert final.status == "completed", final.error
    with TestClient(app) as client:
        projected = client.get(f"/api/v1/rules/{rule['id']}").json()
        validation = projected["validation"]
        assert validation["status"] == "passed"
        assert validation["independent_holdout"]["status"] == "passed"
        assert (
            validation["project_replay"]["status"]
            == "candidate_match_needs_confirmation"
        )
        confirmation = client.post(
            f"/api/v1/rules/{rule['id']}/confirm-project-match",
            json={
                "finding_id": validation["project_replay"]["matched_ids"][0],
                "reason": "Human reviewed the exact saved project replay match",
            },
        )
        assert confirmation.status_code == 200
        assert client.post(f"/api/v1/rules/{rule['id']}/publish").status_code == 200
    assert phases.count("generate_rule") == 1
