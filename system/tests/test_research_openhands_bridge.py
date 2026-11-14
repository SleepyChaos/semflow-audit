"""Web OpenHands requests use the same public repair graph and preserve failures."""

from app.core.audit_config import audit_settings
from app.persistence.stage_models import RepairRecord
from app.research_bridge.models import ResearchBinding
from app.runtime.stages import run_stage
from sqlmodel import Session, select

from tests.research_repair_cases import create_confirmed_repair

IMAGE = "sha256:" + "c" * 64


def proposal():
    return {
        "changes": [
            {
                "file": "app.py",
                "old_text": "eval(input())",
                "new_text": "int(input())",
                "reason": "Replace dynamic evaluation with explicit integer conversion",
            }
        ],
        "summary": "OpenHands selected explicit integer conversion for the frozen target",
    }


def test_web_openhands_uses_public_core_and_projects_needs_review(
    bridge_case, scanner, repair_model, syntax, monkeypatch
):
    monkeypatch.setattr(audit_settings, "OPENHANDS_IMAGE", IMAGE)
    monkeypatch.setattr(audit_settings, "OPENHANDS_PYTHON", "/usr/bin/python")
    monkeypatch.setattr(audit_settings, "OPENHANDS_MAX_STEPS", 4)
    monkeypatch.setattr(
        "semflow_research.repair.repair_openhands.generate",
        lambda *args, **kwargs: {
            "proposal": proposal(),
            "runtime": {"status": "completed", "metrics": {"calls": 1}},
        },
    )
    stage_id = create_confirmed_repair(bridge_case, engine="openhands")
    stage = run_stage(str(stage_id))
    assert stage.status == "completed", (stage.error, stage.result)
    with Session(bridge_case[0]) as session:
        binding = session.exec(
            select(ResearchBinding).where(ResearchBinding.stage_id == stage_id)
        ).one()
        record = session.exec(
            select(RepairRecord).where(RepairRecord.stage_id == stage_id)
        ).one()
        assert binding.executor == "semflow-research/2"
        assert binding.request["inputs"]["engine"] == "openhands"
        assert binding.request["inputs"]["openhands"]["image_digest"] == IMAGE
        assert record.status == "checks_passed"
        assert record.validation["research_manifest"]
    assert repair_model == ["inspect_semantics", "assess_patch_contract"]
    assert syntax == ["value = int(input())\n"]
    assert run_stage(str(stage_id)).status == "completed"


def test_web_openhands_missing_resource_is_explicit_failure_and_never_native(
    bridge_case, scanner, monkeypatch
):
    monkeypatch.setattr(audit_settings, "OPENHANDS_IMAGE", "")
    monkeypatch.setattr(audit_settings, "OPENHANDS_PYTHON", "")
    stage_id = create_confirmed_repair(bridge_case, engine="openhands")
    stage = run_stage(str(stage_id))
    assert stage.status == "failed"
    assert "resource" in (stage.error or "").lower() or stage.result.get("failure")
    with Session(bridge_case[0]) as session:
        binding = session.exec(
            select(ResearchBinding).where(ResearchBinding.stage_id == stage_id)
        ).one()
        assert binding.request == {}
