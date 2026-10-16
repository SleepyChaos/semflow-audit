# ruff: noqa: F811
"""Selected acceptance expectations remain scoped and do not expose test bodies."""

from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from app.domain.audit import AuditError
from app.services.repair_requirements import acceptance_contract

from tests.test_verification_lifecycle import comparison_context  # noqa: F401


def service_for(context):
    return SimpleNamespace(
        inputs=SimpleNamespace(
            verification_suite_id=UUID(context["suite_id"]),
            candidate_ids=[UUID(context["suite"]["cases"][0]["candidate_ids"][0])],
        ),
        stage=SimpleNamespace(audit_id=context["run_id"]),
    )


@pytest.mark.parametrize(
    "pipeline_context",
    [{"app.py": "def calculate(value):\n    return eval(value)\n"}],
    indirect=True,
)
def test_selected_suite_exports_expectations_but_not_executable_oracle(
    comparison_context,
):
    service = service_for(comparison_context)
    result = acceptance_contract(service)
    assert result["suite_id"] == comparison_context["suite_id"]
    assert result["suite_hash"]
    assert {case["expected_behavior"] for case in result["cases"]} == {
        "不得执行输入表达式",
        "仍返回原有整数",
    }
    assert "files" not in result and "assert True" not in str(result)
    service.inputs.candidate_ids = [uuid4()]
    with pytest.raises(AuditError, match="未覆盖"):
        acceptance_contract(service)


@pytest.mark.parametrize(
    "pipeline_context",
    [{"app.py": "def calculate(value):\n    return eval(value)\n"}],
    indirect=True,
)
def test_selected_suite_rejects_tampered_test_files(comparison_context):
    from app.adapters.artifacts import ArtifactStore

    file = (
        ArtifactStore().directory(comparison_context["suite_id"])
        / "tests/test_check.py"
    )
    file.write_text("def test_security(): pass\n")
    with pytest.raises(AuditError):
        acceptance_contract(service_for(comparison_context))


@pytest.mark.parametrize(
    "pipeline_context",
    [{"app.py": "def calculate(value):\n    return eval(value)\n"}],
    indirect=True,
)
def test_production_inspection_can_cite_selected_acceptance_intent_without_claiming_safety(
    comparison_context,
    monkeypatch,
):
    from app.core.db import engine
    from app.persistence.stage_models import StageRun
    from app.persistence.stage_repository import StageRepository
    from app.services.repair import RepairService
    from app.services.repair_semantics import SemanticRepair
    from sqlmodel import Session

    from tests.test_semantic_development import InspectModel, ready

    context = comparison_context
    monkeypatch.setattr(
        "app.adapters.repair.verification_runner.resolve_image",
        lambda image: "sha256:test-only",
    )

    def respond(payload):
        suite_intent = next(
            row
            for row in payload["evidence"]
            if row["kind"] == "repair_request"
            and row["reference"].get("suite_id") == context["suite_id"]
        )
        assert suite_intent["reference"]["suite_hash"]
        assert "不得执行输入表达式" in suite_intent["content"]
        assert "assert True" not in suite_intent["content"]
        value = ready(payload)
        value["facts"].append(
            {
                "statement": "Selected acceptance expects expression input to be rejected",
                "state": "supported",
                "category": "business",
                "critical": True,
                "evidence_ids": [suite_intent["id"]],
            }
        )
        return value

    with Session(engine) as db:
        stage = StageRun(
            audit_id=context["run_id"],
            kind="repair",
            prompt_version="3",
            inputs={
                "candidate_ids": context["suite"]["cases"][0]["candidate_ids"],
                "allowed_paths": [context["name"]],
                "verification_suite_id": context["suite_id"],
                "rescan": False,
            },
        )
        db.add(stage)
        db.commit()
        db.refresh(stage)
        identity = str(stage.id)
    assert StageRepository().claim(identity)
    service = RepairService(identity, InspectModel(respond))
    result = SemanticRepair(service).prepare({})
    assert result["context_hash"]


@pytest.mark.parametrize(
    "pipeline_context",
    [{"app.py": "def calculate(value):\n    return eval(value)\n"}],
    indirect=True,
)
def test_legacy_selected_context_does_not_gain_new_execution_behavior(
    comparison_context, monkeypatch
):
    import json

    from app.core.db import engine
    from app.persistence.stage_models import StageRun
    from app.persistence.stage_repository import StageRepository
    from app.services.context_materials import digest
    from app.services.repair import RepairService
    from app.services.repair_semantics import SemanticRepair
    from sqlmodel import Session

    from tests.test_semantic_development import InspectModel

    context = comparison_context
    monkeypatch.setattr(
        "app.adapters.repair.verification_runner.resolve_image",
        lambda image: "sha256:test-only",
    )
    with Session(engine) as db:
        stage = StageRun(
            audit_id=context["run_id"],
            kind="repair",
            prompt_version="3",
            inputs={
                "candidate_ids": context["suite"]["cases"][0]["candidate_ids"],
                "allowed_paths": [context["name"]],
                "verification_suite_id": context["suite_id"],
                "rescan": False,
            },
        )
        db.add(stage)
        db.commit()
        db.refresh(stage)
        identifier = str(stage.id)
    assert StageRepository().claim(identifier)
    service = RepairService(identifier, InspectModel())
    repair = SemanticRepair(service)
    state = repair.prepare({})
    file = service.directory / "repair-context.json"
    legacy = json.loads(file.read_text())
    legacy["acceptance_contract"].pop("image")
    legacy.pop("verification_image_id")
    legacy.pop("candidate_suite_feedback")
    file.write_text(json.dumps(legacy))
    state["context_hash"] = digest(legacy)
    payload = repair.context(state)
    assert "candidate_suite_feedback" not in payload
    assert "verification_image_id" not in payload
    assert "image" not in payload["acceptance_contract"]
    assert service.provider.usage["calls"] == 1
