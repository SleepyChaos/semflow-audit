"""Only unfinished windows are retried; history and evidence remain immutable."""

import json

import pytest
from app.api.routes import stages
from app.core.db import engine
from app.domain.audit import AuditError
from app.persistence.stage_models import Candidate, StageRun
from app.persistence.stage_repository import StageRepository
from app.services.scouting import ScoutService
from app.workflows.scouting import build_scout_graph
from sqlmodel import Session, select

from tests.test_dual_discovery import HypothesisModel, run_scout


@pytest.mark.parametrize(
    "pipeline_context",
    [{f"module{i}.py": "value = 1\n" for i in range(3)}],
    indirect=True,
)
def test_continue_retries_failed_and_unvisited_windows_preserving_history(
    pipeline_context, monkeypatch
):
    class Interrupted(HypothesisModel):
        def generate(self, *args):
            if self.usage["calls"]:
                raise AuditError("temporary provider failure", code="provider_error")
            return super().generate(*args)

    previous_service = run_scout(pipeline_context, Interrupted(), version="4")
    previous = previous_service.repository.get(previous_service.stage_id)
    completed = {
        r["unit_id"] for r in previous.result["units"] if r["status"] == "inspected"
    }
    assert (
        len(completed) == 1 and previous.result["coverage"]["uninspected_windows"] == 2
    )
    monkeypatch.setattr(stages.execute_stage, "delay", lambda *_: None)
    client = pipeline_context["client"]
    response = client.post(f"/api/v1/stages/{previous.id}/continue-scout")
    assert response.status_code == 201, response.text
    identifier = response.json()["id"]
    assert response.json()["result"]["source_stage_ids"] == [str(previous.id)]
    assert (
        client.post(f"/api/v1/stages/{previous.id}/continue-scout").status_code == 409
    )
    StageRepository().claim(identifier)
    model = HypothesisModel()
    service = ScoutService(identifier, model)
    build_scout_graph(service).invoke({"stage_id": identifier})
    assert len(model.seen) == 2
    assert not completed.intersection(p["unit"]["id"] for p in model.seen)
    result = service.repository.get(identifier).result
    assert result["coverage"]["inspected_windows"] == 3
    assert result["coverage"]["uninspected_windows"] == 0
    assert previous_service.repository.get(str(previous.id)).result == previous.result
    with Session(engine) as db:
        candidates = db.exec(
            select(Candidate).where(Candidate.audit_id == previous.audit_id)
        ).all()
        assert len(candidates) == 3
        assert sum(c.stage_id == previous.id for c in candidates) == 1
        assert all(c.evidence_ids for c in candidates)
        assert db.get(StageRun, previous.id).status == "completed"
    assert client.post(f"/api/v1/stages/{identifier}/continue-scout").status_code == 409


@pytest.mark.parametrize(
    "pipeline_context",
    [{"a.py": "value = 1\n", "b.py": "value = 2\n"}],
    indirect=True,
)
def test_continue_rejects_modified_map_and_foreign_stage(pipeline_context, monkeypatch):
    service = run_scout(pipeline_context, version="4", max_units=1)
    monkeypatch.setattr(stages.execute_stage, "delay", lambda *_: None)
    path = service.directory / "scout-map.json"
    project = json.loads(path.read_text())
    project["snapshot"] = "modified-snapshot"
    path.write_text(json.dumps(project))
    response = pipeline_context["client"].post(
        f"/api/v1/stages/{service.stage_id}/continue-scout"
    )
    assert response.status_code == 409 and "快照" in response.text
    from uuid import uuid4

    from app.api.deps import get_workspace
    from app.main import app
    from app.persistence.workspace import Workspace

    monkeypatch.setitem(
        app.dependency_overrides, get_workspace, lambda: Workspace(uuid4())
    )
    assert (
        pipeline_context["client"]
        .post(f"/api/v1/stages/{service.stage_id}/continue-scout")
        .status_code
        == 404
    )
