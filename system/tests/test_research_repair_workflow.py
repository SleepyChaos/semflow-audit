"""RepairPanel's unchanged suite/rescan workflow runs the shared research kernel."""

import json
from uuid import UUID

import pytest
from app.main import app
from app.persistence.audit_models import AuditRun
from app.persistence.stage_models import RepairRecord, StageFollowup, StageRun
from app.research_bridge.models import ResearchBinding
from app.runtime.stages import run_stage
from fastapi.testclient import TestClient
from semflow_research.adapters.ai import provider
from semflow_research.adapters.codeql.scanner import CodeQLScanner
from sqlmodel import Session, select

from tests.research_repair_cases import request_from_panel


@pytest.mark.parametrize("origin", ["generated", "imported"])
@pytest.mark.parametrize("engine", ["native", "openhands"])
def test_existing_web_suite_rescan_followup_and_human_acceptance(
    bridge_case,
    scanner,
    suite_model,
    repair_model,
    syntax,
    suite_runner,
    monkeypatch,
    origin,
    engine,
    tmp_path,
):
    if engine == "openhands":
        from app.core.audit_config import audit_settings

        from research.tests.openhands_process_cases import resources

        configured = resources(tmp_path, audit_settings, monkeypatch)
        for field in ("OPENHANDS_PYTHON", "OPENHANDS_IMAGE", "OPENHANDS_RUNNER"):
            monkeypatch.setattr(audit_settings, field, getattr(configured, field))
    # Get a confirmed target through the standard fixture, then cancel its
    # initially queued request so the real API can create the selected-suite run.
    queued, audit_id = request_from_panel(bridge_case, monkeypatch)
    with Session(bridge_case[0]) as session:
        previous = session.get(StageRun, queued)
        candidate_ids = previous.inputs["candidate_ids"]
        previous.status = "cancelled"
        session.add(previous)
        session.commit()
    repair_factory = provider.OpenAI
    monkeypatch.setattr(provider, "OpenAI", suite_model.factory)
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/audits/{audit_id}/verification-suites/generate",
            json={
                "candidate_ids": candidate_ids,
                "requirements": "Accept integer input and reject expression evaluation",
            },
        )
        assert response.status_code == 201, response.text
        suite_id = UUID(response.json()["id"])
    built = run_stage(str(suite_id))
    assert built.status == "completed", (built.error, built.result)
    assert len(suite_model.calls) == 1
    assert suite_runner == []  # generation is not an executed acceptance test
    with TestClient(app) as client:
        suites = client.get(f"/api/v1/audits/{audit_id}/verification-suites")
        assert suites.status_code == 200, suites.text
        assert suites.json()[0]["candidate_ids"] == candidate_ids
    if origin == "imported":
        definition = built.result["suite"]
        definition = {
            **definition,
            "title": "输入验证测试",
            "summary": "输入应拒绝动态表达式并保留正常数字输入的功能行为",
            "cases": [
                {
                    **case,
                    "input_description": "测试输入：" + case["input_description"],
                    "expected_behavior": "预期行为：" + case["expected_behavior"],
                }
                for case in definition["cases"]
            ],
        }
        from research.tests.suite_cases import IMAGE

        with TestClient(app) as client:
            response = client.post(
                f"/api/v1/audits/{audit_id}/verification-suites/import",
                json={"suite": definition, "image": IMAGE},
            )
            assert response.status_code == 201, response.text
            suite_id = UUID(response.json()["id"])
    monkeypatch.setattr(provider, "OpenAI", repair_factory)
    analyze = CodeQLScanner.analyze

    def patched(self, database, output, log, plan):
        analyze(self, database, output, log, plan)
        if database.name == "patched-database":
            value = json.loads(output.read_text())
            value["runs"][0]["results"] = []
            output.write_text(json.dumps(value))

    monkeypatch.setattr(CodeQLScanner, "analyze", patched)
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/audits/{audit_id}/repair",
            json={
                "engine": engine,
                "candidate_ids": candidate_ids,
                "allowed_paths": [],
                "validation_profile": "syntax",
                "rescan": True,
                "verification_suite_id": str(suite_id),
            },
        )
        assert response.status_code == 201, response.text
        repair_stage_id = UUID(response.json()["id"])
    repaired = run_stage(str(repair_stage_id))
    assert repaired.status == "completed", (repaired.error, repaired.result)
    with Session(bridge_case[0]) as session:
        record = session.exec(
            select(RepairRecord).where(RepairRecord.stage_id == repair_stage_id)
        ).one()
        record_id = record.id
        assert record.status == "checks_passed", record.validation
        assert record.validation["selected_suite"]["status"] == "passed"
        assert record.validation["rescan"]["status"] == "passed"
        from app.adapters.artifacts import ArtifactStore
        from app.adapters.snapshot import snapshot_digest

        assert record.validation["rescan"]["patched_snapshot_hash"] == snapshot_digest(
            ArtifactStore().directory(str(repair_stage_id)) / "workspace"
        )
        assert record.validation["selected_suite"]["identity"]["suite_id"] == str(
            suite_id
        )
        assert (
            record.validation["selected_suite"]["identity"]["source_snapshot"]
            == session.get(AuditRun, audit_id).snapshot_hash
        )
        assert record.validation["selected_suite"]["research_identity"][
            "suite_id"
        ] != str(suite_id)
        assert record.validation["isolated_tests"]["status"] == "not_run"
        followup = session.exec(
            select(StageFollowup).where(
                StageFollowup.source_stage_id == repair_stage_id
            )
        ).one()
        assert followup.status == "delivered", followup.error
        compare_id = followup.target_stage_id
        assert session.exec(
            select(ResearchBinding).where(ResearchBinding.stage_id == compare_id)
        ).one()
    # No model can be constructed for the independent follow-up comparison.
    monkeypatch.setattr(
        provider,
        "OpenAI",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("comparison model")),
    )
    verified = run_stage(str(compare_id))
    assert verified.status == "completed", (verified.error, verified.result)
    assert verified.result["status"] == "passed"
    assert verified.usage["calls"] == 0
    with TestClient(app) as client:
        rows = client.get(f"/api/v1/audits/{audit_id}/repairs").json()
        assert rows[0]["comparison"]["status"] == "passed", rows
        assert rows[0]["acceptance_ready"] is True, rows
        assert rows[0]["status"] != "accepted"
        response = client.post(
            f"/api/v1/repairs/{record_id}/accept",
            json={
                "test_reviewed": False,
                "comparison_stage_id": str(compare_id),
                "reason": "Reviewed tests and patch against the intended input policy",
            },
        )
        assert response.status_code == 409
        response = client.post(
            f"/api/v1/repairs/{record_id}/accept",
            json={
                "test_reviewed": True,
                "comparison_stage_id": str(compare_id),
                "reason": "Reviewed tests and patch against the intended input policy",
            },
        )
        assert response.status_code == 200, response.text
        assert client.get(f"/api/v1/repairs/{record_id}/diff").status_code == 200
        assert (
            client.get(f"/api/v1/stages/{repair_stage_id}/materials").status_code == 200
        )
    count = len(suite_runner)
    assert run_stage(str(repair_stage_id)).status == "completed"
    assert run_stage(str(compare_id)).status == "completed"
    assert len(suite_runner) == count
    with Session(bridge_case[0]) as session:
        assert session.get(RepairRecord, record_id).status == "accepted"
        audit = session.get(AuditRun, audit_id)
        from app.adapters.artifacts import ArtifactStore

        assert (
            ArtifactStore().source(str(audit.source_run_id)) / "app.py"
        ).read_text() == "value = eval(input())\n"
