"""Web scan dispatch and downloadable SARIF use the independent discovery kernel."""

from app.core.audit_config import audit_settings
from app.main import app
from app.persistence.stage_models import StageRun
from app.research_bridge.models import ResearchAuditBinding, ResearchBinding
from app.research_bridge.requests import research_root
from app.runtime.scans import run_scan
from fastapi.testclient import TestClient
from semflow_research.public.runs import inspect
from sqlmodel import Session, select


def test_new_scan_uses_public_kernel_and_keeps_old_sarif_api(bridge_case, scanner):
    db, _, _, _ = bridge_case
    audit = upload(bridge_case)
    result = run_scan(str(audit.id))
    assert result.status == "completed", result.error
    assert scanner == ["database", "analyze"]
    with Session(db) as session:
        binding = session.exec(
            select(ResearchAuditBinding).where(
                ResearchAuditBinding.audit_id == audit.id
            )
        ).one()
        receipt = inspect(binding.execution_id, root=research_root())
        assert receipt.execution_status == "completed"
        assert receipt.result.baseline is not None
        assert binding.execution_id != audit.id
        assert result.findings[0]["locations"][0]["file"] == "app.py"
        assert (
            result.coverage["research_receipt"]["legacy_source_digest"]
            == result.snapshot_hash
        )
    run_scan(str(audit.id))
    assert scanner == ["database", "analyze"]
    with TestClient(app) as client:
        sarif = client.get(f"/api/v1/audits/{audit.id}/sarif")
        assert sarif.status_code == 200
        assert sarif.json()["runs"][0]["results"][0]["ruleId"] == "py/code-injection"


def test_optional_model_failure_keeps_real_static_findings_and_failed_scout(
    bridge_case, scanner, monkeypatch
):
    db, _, _, _ = bridge_case
    monkeypatch.setattr(audit_settings, "AI_BASE_URL", "")
    audit = upload(bridge_case, dual=True)
    result = run_scan(str(audit.id))
    assert result.status == "completed", result.error
    assert scanner == ["database", "analyze"]
    assert len(result.findings) == 1
    assert result.coverage["dual_engine"]["status"] == "partial"
    assert result.coverage["dual_engine"]["scout"]["status"] == "failed"
    with Session(db) as session:
        binding = session.exec(
            select(ResearchAuditBinding).where(
                ResearchAuditBinding.audit_id == audit.id
            )
        ).one()
        scout = session.get(StageRun, binding.scout_stage_id)
        assert scout.status == "failed" and scout.error
        child = session.exec(
            select(ResearchBinding).where(ResearchBinding.stage_id == scout.id)
        ).one()
        assert child.manifest is not None


def test_bad_sarif_remains_failed_and_is_not_a_successful_empty_scan(
    bridge_case, scanner, monkeypatch
):
    monkeypatch.setattr(
        "semflow_research.adapters.codeql.scanner.CodeQLScanner.analyze",
        lambda self, database, output, log, plan: output.write_text("{broken"),
    )
    audit = upload(bridge_case)
    result = run_scan(str(audit.id))
    assert result.status == "failed" and result.error
    assert result.findings == []
    db, _, _, _ = bridge_case
    with Session(db) as session:
        binding = session.exec(
            select(ResearchAuditBinding).where(
                ResearchAuditBinding.audit_id == audit.id
            )
        ).one()
        receipt = inspect(binding.execution_id, root=research_root())
        assert receipt.failure.code == "parse_failed"
        assert receipt.result is None


from tests.research_bridge_cases import upload
