from datetime import timedelta
from uuid import uuid4

from app.api.deps import get_workspace
from app.core.db import engine
from app.jobs.stages import execute_stage
from app.main import app
from app.models import User
from app.persistence.stage_models import StageRun
from app.persistence.stage_repository import StageRepository
from app.persistence.workspace import Workspace
from sqlmodel import Session, delete


def test_stage_dispatch_failure_and_independent_retry(pipeline_context, monkeypatch):
    api = pipeline_context["client"]
    run_id = pipeline_context["run_id"]

    def offline(*_):
        raise ConnectionError("unavailable")

    monkeypatch.setattr(execute_stage, "delay", offline)
    response = api.post(f"/api/v1/audits/{run_id}/review", json={"discover": True})
    assert response.status_code == 201
    original = response.json()
    assert original["status"] == "failed" and "队列" in original["error"]
    monkeypatch.setattr(execute_stage, "delay", lambda *_: None)
    retry = api.post(f"/api/v1/stages/{original['id']}/retry").json()
    assert retry["id"] != original["id"] and retry["status"] == "queued"
    assert api.get(f"/api/v1/stages/{original['id']}").json()["status"] == "failed"
    assert api.post(f"/api/v1/stages/{retry['id']}/cancel").status_code == 200
    assert StageRepository().claim(retry["id"]) is False


def test_workspace_stage_evidence_and_report_access(pipeline_context, monkeypatch):
    ctx = pipeline_context
    api = ctx["client"]
    with Session(engine) as session:
        stage = StageRun(audit_id=ctx["run_id"], kind="review", status="completed")
        session.add(stage)
        session.commit()
        session.refresh(stage)
        stage_id = str(stage.id)
        other = User(
            id=uuid4(), email=f"{uuid4()}@example.com", hashed_password="test-only"
        )
        session.add(other)
        session.commit()
        session.refresh(other)
        other_id = other.id
    monkeypatch.setitem(
        app.dependency_overrides, get_workspace, lambda: Workspace(other_id)
    )
    for endpoint in [
        f"/stages/{stage_id}",
        f"/stages/{stage_id}/evidence",
        f"/stages/{stage_id}/logs",
        f"/audits/{ctx['run_id']}/report",
        f"/audits/{ctx['run_id']}/candidates",
        f"/audits/{ctx['run_id']}/repairs",
    ]:
        assert api.get("/api/v1" + endpoint).status_code == 404
    monkeypatch.setitem(
        app.dependency_overrides, get_workspace, lambda: Workspace(ctx["owner"])
    )
    with Session(engine) as session:
        session.exec(delete(User).where(User.id == other_id))
        session.commit()


def test_manual_evidence_is_real_and_contained(pipeline_context):
    api = pipeline_context["client"]
    run_id = pipeline_context["run_id"]
    response = api.post(
        f"/api/v1/audits/{run_id}/evidence",
        params={"file": "app.py", "start_line": 1, "end_line": 1},
    )
    assert response.status_code == 201
    assert response.json()["content"] == "value = eval(input())"
    assert (
        api.post(
            f"/api/v1/audits/{run_id}/evidence", params={"file": "../outside"}
        ).status_code
        == 422
    )


def test_stage_recovery_prevents_late_completion(pipeline_context):
    import pytest
    from app.models import get_datetime_utc
    from app.persistence.stage_repository import StageCancelled

    ctx = pipeline_context
    with Session(engine) as session:
        stage = StageRun(
            audit_id=ctx["run_id"],
            kind="review",
            status="running",
            updated_at=get_datetime_utc() - timedelta(minutes=46),
        )
        session.add(stage)
        session.commit()
        session.refresh(stage)
        identifier = str(stage.id)
    response = ctx["client"].post(f"/api/v1/stages/{identifier}/recover")
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    with pytest.raises(StageCancelled):
        StageRepository().update(identifier, status="completed")
    assert StageRepository().get(identifier).status == "cancelled"


def test_failed_manual_evidence_cannot_be_dispatched_as_ai_stage(pipeline_context):
    ctx = pipeline_context
    api = ctx["client"]
    assert (
        api.post(
            f"/api/v1/audits/{ctx['run_id']}/evidence", params={"file": "../outside"}
        ).status_code
        == 422
    )
    stage = next(
        row
        for row in api.get(f"/api/v1/audits/{ctx['run_id']}/stages").json()
        if row["kind"] == "manual_evidence"
    )
    assert api.post(f"/api/v1/stages/{stage['id']}/retry").status_code == 409
