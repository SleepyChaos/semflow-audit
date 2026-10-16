"""Consistency checks reject unrelated behavior drift and incomplete assessments."""

from types import SimpleNamespace

import pytest
from app.domain.audit import AuditError
from app.services.repair_consistency import check_contract

from tests.test_semantic_development import InspectModel


def repair(tmp_path, callback):
    evidence = {
        "id": "real-source",
        "kind": "code",
        "reference": {"file": "app.py", "start_line": 1, "end_line": 1},
        "content": "return match(value)",
        "digest": "fixture",
    }
    return SimpleNamespace(
        directory=tmp_path,
        service=SimpleNamespace(provider=InspectModel(callback)),
        context=lambda _: {
            "targets": [{"description": "Change only resource path behavior"}],
            "allowed_files": {"app.py": "return match(value)"},
            "inspection": {
                "view": {
                    "facts": [
                        {
                            "critical": True,
                            "statement": "Shared helper preserves header matching",
                            "evidence_ids": ["real-source"],
                        }
                    ],
                    "modification_semantics": "Preserve unrelated behavior",
                },
                "evidence": [evidence],
            },
        },
    )


def response(payload):
    return {
        "constraints": [
            {
                "fact_index": 0,
                "status": "conflicting",
                "explanation": "Shared helper change also changes unrelated header matching",
                "evidence_ids": ["real-source"],
            }
        ],
        "behavior_conflicts": ["Unrelated caller behavior changed"],
        "limitation": "Model observation requires actual execution and acceptance",
    }


def test_conflicting_shared_helper_is_not_treated_as_syntax_success(tmp_path):
    result = check_contract(
        repair(tmp_path, response), {"attempt": 1, "proposal": {"changes": []}}
    )
    assert result["status"] == "failed"
    assert "unrelated header" in result["output"]


@pytest.mark.parametrize("failure", ["citation", "coverage"])
def test_check_requires_real_citations_and_each_critical_fact(tmp_path, failure):
    def reply(payload):
        value = response(payload)
        value["constraints"][0]["evidence_ids"] = (
            ["invented"] if failure == "citation" else ["real-source"]
        )
        value["constraints"][0]["fact_index"] = 1 if failure == "coverage" else 0
        return value

    with pytest.raises(AuditError, match="未覆盖必需事实或引用无效"):
        check_contract(
            repair(tmp_path, reply), {"attempt": 1, "proposal": {"changes": []}}
        )


def test_contract_failure_diagnosis_reuses_assessment_and_stops_unknowns():
    from app.services.repair_consistency import contract_diagnosis

    checks = {
        "isolated_tests": {"status": "passed"},
        "semantic_contract": {
            "status": "failed",
            "output": "Unknown unrelated caller compatibility",
            "assessment": {
                "constraints": [
                    {"status": "unknown", "explanation": "Actual caller was not read"}
                ],
                "behavior_conflicts": [],
            },
        },
    }
    assert contract_diagnosis(checks)["category"] == "inconclusive"
    checks["semantic_contract"]["assessment"]["constraints"][0]["status"] = (
        "conflicting"
    )
    assert contract_diagnosis(checks)["category"] == "implementation"
    checks["isolated_tests"]["status"] = "failed"
    assert contract_diagnosis(checks) is None


def test_wrong_interpretation_goes_back_to_understanding_not_patch_conformity():
    from app.services.repair_consistency import contract_diagnosis

    checks = {
        "isolated_tests": {"status": "passed"},
        "semantic_contract": {
            "status": "failed",
            "output": "The interpretation expands the request to unrelated callers",
            "assessment": {
                "constraints": [
                    {
                        "status": "consistent",
                        "explanation": "Patch agrees with the model view",
                    }
                ],
                "behavior_conflicts": [],
                "interpretation_conflicts": [
                    "Model interpretation extends beyond user authorized flow"
                ],
            },
        },
    }
    result = contract_diagnosis(checks)
    assert result["category"] == "understanding"
    assert "extends beyond" in result["violated_constraints"][0]
    assert "prior model view" in result["next_action"]


@pytest.mark.parametrize("case", ["missing", "wrong_source", "correct"])
def test_each_caller_requires_its_own_read_body(tmp_path, monkeypatch, case):
    from app.adapters.repair import impact

    caller = {
        "id": "read-caller",
        "kind": "code",
        "reference": {"file": "caller.py", "start_line": 1, "end_line": 1},
        "content": "match(value)",
        "digest": "fixture",
    }
    monkeypatch.setattr(
        impact,
        "caller_obligations",
        lambda *args: {
            "obligations": [{"id": 0, "evidence_id": caller["id"]}],
            "evidence": [caller],
        },
    )

    def reply(payload):
        value = response(payload)
        if case != "missing":
            value["callers"] = [
                {
                    "obligation_id": 0,
                    "status": "conflicting",
                    "explanation": "Existing unrelated caller changes behavior",
                    "evidence_ids": ["read-caller"]
                    if case == "correct"
                    else ["real-source"],
                }
            ]
        return value

    instance = repair(tmp_path, reply)
    instance.service.evidence = SimpleNamespace()
    state = {"attempt": 1, "proposal": {"changes": []}}
    if case == "correct":
        assert check_contract(instance, state)["status"] == "failed"
    else:
        with pytest.raises(AuditError, match="共享函数调用影响检查不完整"):
            check_contract(instance, state)


def test_caller_feedback_cannot_invent_a_source_identifier(pipeline_context):
    from uuid import uuid4

    from app.services.repair_consistency import impact_materials

    from tests.test_semantic_development import InspectModel, repair_service

    service = repair_service(pipeline_context, InspectModel())
    with pytest.raises(AuditError):
        impact_materials(
            service,
            {
                "semantic_contract": {
                    "caller_impact": {"obligations": [{"evidence_id": str(uuid4())}]}
                }
            },
        )
