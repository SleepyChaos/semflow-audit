"""Opt-in Web/native bridge gate with real Docker; model/confirmation are test fixtures."""

import json
import os
import shutil
from pathlib import Path

import pytest
from app.adapters.artifacts import ArtifactStore
from app.core.audit_config import audit_settings
from app.persistence.stage_models import RepairRecord
from app.research_bridge.models import ResearchBinding
from app.research_bridge.requests import research_root
from app.runtime.stages import run_stage
from semflow_research.public.runs import inspect
from sqlmodel import Session, select

from tests.research_repair_cases import create_confirmed_repair


@pytest.mark.integration
@pytest.mark.skipif(
    os.environ.get("AUDIT_RUN_REAL_TOOLS") != "1", reason="explicit real Docker opt-in"
)
def test_native_web_bridge_with_actual_docker_validator(
    bridge_case, scanner, repair_model, monkeypatch
):
    monkeypatch.setattr(
        audit_settings,
        "VALIDATOR_PYTHON_IMAGE",
        os.environ["SEMFLOW_RESEARCH_VALIDATOR_IMAGE"],
    )
    stage_id = create_confirmed_repair(bridge_case)
    stage = run_stage(str(stage_id))
    assert stage.status == "completed", stage.error
    with Session(bridge_case[0]) as session:
        binding = session.exec(
            select(ResearchBinding).where(ResearchBinding.stage_id == stage_id)
        ).one()
        record = session.exec(
            select(RepairRecord).where(RepairRecord.stage_id == stage_id)
        ).one()
        receipt = inspect(binding.execution_id, root=research_root())
        assert record.status == "checks_passed"
        assert record.validation["syntax"]["status"] == "passed"
        assert "Python syntax checks passed: 1" in record.validation["syntax"]["output"]
        assert (
            record.validation["syntax"]["image_id"]
            == os.environ["SEMFLOW_RESEARCH_VALIDATOR_IMAGE"]
        )
        assert receipt.usage.calls == 3 and len(repair_model) == 3
        assert record.candidate_ids == stage.inputs["candidate_ids"]
        output = os.environ.get("SEMFLOW_RESEARCH_GATE_REPORT")
        if output:
            target = Path(output) / str(binding.execution_id)
            target.mkdir(parents=True, exist_ok=False)
            shutil.copytree(research_root(), target / "research")
            shutil.copytree(
                ArtifactStore().directory(str(stage_id)), target / "platform-view"
            )
            (target / "receipt.json").write_text(receipt.model_dump_json(indent=2))
            (target / "binding.json").write_text(binding.model_dump_json(indent=2))
            (target / "record.json").write_text(record.model_dump_json(indent=2))
            (target / "scope.json").write_text(
                json.dumps(
                    {
                        "scope": "real Web worker, bridge, native graph, immutable receipts, platform projection and Docker syntax validator",
                        "substitutes": [
                            "external model",
                            "explicit operator confirmation",
                            "upstream scanner",
                        ],
                        "limits": "one synthetic source; syntax is not vulnerability efficacy, before/after validation or human acceptance",
                        "stage_id": str(stage_id),
                        "execution_id": str(binding.execution_id),
                        "input_digest": receipt.input_digest,
                    },
                    indent=2,
                )
            )
