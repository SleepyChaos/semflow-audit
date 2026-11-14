"""Unmodified RepairPanel rescan request traverses API/worker/native/projection."""

import json

import pytest
from app.adapters.artifacts import ArtifactStore
from app.main import app
from app.persistence.stage_models import RepairRecord
from app.research_bridge.models import ResearchBinding
from app.research_bridge.requests import research_root
from app.runtime.stages import run_stage
from fastapi.testclient import TestClient
from semflow_research.adapters.codeql.scanner import CodeQLScanner
from semflow_research.domain.errors import AuditError
from semflow_research.public.runs import inspect
from sqlmodel import Session, select

from tests.research_repair_cases import request_from_panel


@pytest.mark.parametrize(
    "mode", ["clear", "remaining", "tool_failed", "parse_failed", "unlinked"]
)
def test_panel_rescan_keeps_actual_baseline_and_separate_technical_outcomes(
    bridge_case, scanner, repair_model, syntax, monkeypatch, mode
):
    stage_id, audit_id = request_from_panel(
        bridge_case, monkeypatch, link_static=mode != "unlinked"
    )
    analyze = CodeQLScanner.analyze

    def patched(self, database, output, log, plan):
        if database.name == "patched-database":
            if mode == "tool_failed":
                raise AuditError("injected scanner failure")
            if mode == "parse_failed":
                output.write_text("invalid SARIF")
                return
            analyze(self, database, output, log, plan)
            if mode != "remaining":
                value = json.loads(output.read_text())
                value["runs"][0]["results"] = []
                output.write_text(json.dumps(value))
        else:
            analyze(self, database, output, log, plan)

    monkeypatch.setattr(CodeQLScanner, "analyze", patched)
    source = ArtifactStore().source(str(audit_id))
    original = (source / "app.py").read_bytes()
    stage = run_stage(str(stage_id))
    assert stage.status == "completed", (stage.error, stage.result)
    with Session(bridge_case[0]) as session:
        binding = session.exec(
            select(ResearchBinding).where(ResearchBinding.stage_id == stage_id)
        ).one()
        record = session.exec(
            select(RepairRecord).where(RepairRecord.stage_id == stage_id)
        ).one()
        receipt = inspect(binding.execution_id, root=research_root())
        spec = binding.request
        check = record.validation["rescan"]
        assert (
            spec["inputs"]["validation_plan"]["static_baseline"]["database"]["kind"]
            == "codeql_database"
        )
        assert (
            receipt.result.checks[0].status == "passed"
        )  # syntax is retained on scanner failure
        expected = (
            "passed"
            if mode == "clear"
            else "error"
            if mode.endswith("failed")
            else "needs_review"
        )
        assert check["status"] == expected
        assert record.status == ("checks_passed" if mode == "clear" else "needs_review")
        if mode.endswith("failed"):
            assert check["code"] == mode and check["findings"] is None
        if mode == "remaining":
            assert check["remaining_target_rules"] == ["py/code-injection"]
        assert (source / "app.py").read_bytes() == original
        assert len(syntax) == 1
        record_id = record.id
    with TestClient(app) as client:
        listed = client.get(f"/api/v1/audits/{audit_id}/repairs").json()
        assert listed[0]["validation"]["rescan"]["status"] == expected
        assert listed[0]["acceptance_ready"] is False
        assert client.get(f"/api/v1/repairs/{record_id}/diff").status_code == 200
    count = len(repair_model)
    assert run_stage(str(stage_id)).status == "completed"
    assert len(repair_model) == count
