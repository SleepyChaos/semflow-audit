"""Exercise real API/stage/kernel setup while substituting only external services."""

import json
from types import SimpleNamespace
from uuid import UUID

from app.main import app
from app.persistence.stage_models import RepairRecord, StageFollowup, StageRun
from app.runtime.stages import run_stage
from fastapi.testclient import TestClient
from semflow_research.adapters.ai import provider
from semflow_research.adapters.codeql.scanner import CodeQLScanner
from sqlmodel import Session, select

from tests.research_repair_cases import request_from_panel


def suite_ready(case, monkeypatch, suite_model):
    queued, audit_id = request_from_panel(case, monkeypatch)
    with Session(case[0]) as session:
        stage = session.get(StageRun, queued)
        candidates = stage.inputs["candidate_ids"]
        stage.status = "cancelled"
        session.add(stage)
        session.commit()
    repair_factory = provider.OpenAI
    monkeypatch.setattr(provider, "OpenAI", suite_model.factory)
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/audits/{audit_id}/verification-suites/generate",
            json={
                "candidate_ids": candidates,
                "requirements": "Preserve integer input and reject expressions",
            },
        )
        assert response.status_code == 201, response.text
        suite_id = UUID(response.json()["id"])
    built = run_stage(str(suite_id))
    assert built.status == "completed", (built.error, built.result)
    monkeypatch.setattr(provider, "OpenAI", repair_factory)
    analyze = CodeQLScanner.analyze

    def patched(self, database, output, log, plan):
        analyze(self, database, output, log, plan)
        if database.name == "patched-database":
            document = json.loads(output.read_text())
            document["runs"][0]["results"] = []
            output.write_text(json.dumps(document))

    monkeypatch.setattr(CodeQLScanner, "analyze", patched)
    return SimpleNamespace(audit_id=audit_id, candidates=candidates, suite_id=suite_id)


def repair_ready(case, monkeypatch, setup, *, profile="syntax"):
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/audits/{setup.audit_id}/repair",
            json={
                "candidate_ids": setup.candidates,
                "allowed_paths": [],
                "validation_profile": profile,
                "rescan": True,
                "verification_suite_id": str(setup.suite_id),
            },
        )
        assert response.status_code == 201, response.text
        stage_id = UUID(response.json()["id"])
    completed = run_stage(str(stage_id))
    assert completed.status == "completed", (completed.error, completed.result)
    with Session(case[0]) as session:
        followup = session.exec(
            select(StageFollowup).where(StageFollowup.source_stage_id == stage_id)
        ).one()
        record = session.exec(
            select(RepairRecord).where(RepairRecord.stage_id == stage_id)
        ).one()
        return SimpleNamespace(
            stage_id=stage_id,
            comparison_id=followup.target_stage_id,
            record_id=record.id,
            followup_status=followup.status,
        )
