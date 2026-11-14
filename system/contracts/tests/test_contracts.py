from copy import deepcopy

import pytest
from pydantic import ValidationError
from research_cases import (
    IDENTIFIER,
    model_fields,
    ref,
    repair_spec,
    rules_spec,
    scan_spec,
    target_bundle,
)
from semflow_contracts.actions import ControlCommand
from semflow_contracts.common import ArtifactRef
from semflow_contracts.discovery import AssessmentRecord
from semflow_contracts.evidence import EvidenceRecord
from semflow_contracts.runs import RUN_ADAPTER, validate_spec
from semflow_contracts.validation import ValidationReceipt


@pytest.mark.parametrize("factory", [scan_spec, repair_spec, rules_spec])
def test_all_three_modules_round_trip_without_platform_identity(factory):
    value = factory()
    validated = validate_spec(value)
    assert validate_spec(validated).model_dump(mode="json") == validated.model_dump(
        mode="json"
    )
    assert validated.module == value["module"]
    assert "audit_id" not in validated.model_dump()


@pytest.mark.parametrize(
    "path", ["../outside", "/etc/passwd", "a/../b", "a\\b", "a:b", "a//b", "./b", "."]
)
def test_artifact_paths_cannot_escape_or_alias(path):
    with pytest.raises(ValidationError):
        ArtifactRef.model_validate({**ref(), "path": path})


@pytest.mark.parametrize(
    "change",
    [
        {"schema_version": "semflow.research.run/2.0"},
        {"operation": "verify"},
        {"api_key": "test-only-key"},
        {"audit_id": IDENTIFIER},
    ],
)
def test_invalid_version_operation_and_platform_fields_are_rejected(change):
    with pytest.raises(ValidationError):
        validate_spec({**scan_spec(), **change})


def test_no_implicit_budget_model_or_target_defaults():
    value = repair_spec()
    value["inputs"]["targets"]["snapshot_id"] = IDENTIFIER
    with pytest.raises(ValidationError, match="different source"):
        validate_spec(value)
    value = repair_spec()
    value["prompts"] = []
    with pytest.raises(ValidationError, match="explicit frozen"):
        validate_spec(value)
    value = scan_spec()
    value["policy"]["max_calls"] = None
    with pytest.raises(ValidationError, match="all three"):
        validate_spec(value)


def test_vector_mode_cannot_silently_fall_back_to_bm25():
    value = rules_spec()
    value["inputs"]["retrieval"]["mode"] = "hybrid"
    with pytest.raises(ValidationError, match="embedding/index"):
        validate_spec(value)


def test_structured_but_foreign_evidence_is_rejected():
    value = {
        "evidence_id": IDENTIFIER,
        "execution_id": IDENTIFIER,
        "snapshot_id": IDENTIFIER,
        "kind": "code",
        "content": ref("source_slice"),
        "digest": "0" * 64,
        "location": {
            "snapshot_id": "22222222-2222-4222-8222-222222222222",
            "path": "app.py",
            "start_line": 1,
            "end_line": 1,
            "file_sha256": "0" * 64,
        },
        "provenance": {"producer": "test-only"},
    }
    with pytest.raises(ValidationError, match="identity or range"):
        EvidenceRecord.model_validate(value)
    value["location"]["snapshot_id"] = IDENTIFIER
    value["digest"] = "1" * 64
    with pytest.raises(ValidationError, match="digest"):
        EvidenceRecord.model_validate(value)


def test_model_exclusion_requires_actual_counter_evidence():
    entity = {
        "execution_id": IDENTIFIER,
        "entity_id": IDENTIFIER,
        "bundle": ref("candidate_bundle"),
    }
    with pytest.raises(ValidationError, match="counter-evidence"):
        AssessmentRecord.model_validate(
            {
                "assessment_id": IDENTIFIER,
                "candidate_ref": entity,
                "conclusion": "excluded",
                "checked_premises": [],
                "unknown_premises": [],
                "evidence_refs": [entity],
                "reason": "Synthetic assessment without actual counter-evidence",
            }
        )


def test_empty_checks_are_not_successful_validation():
    with pytest.raises(ValidationError, match="passed checks"):
        ValidationReceipt.model_validate(
            {
                "validation_id": IDENTIFIER,
                "kind": "rule_development",
                "status": "passed",
                "subject_refs": [ref("query")],
                "identity_digest": "0" * 64,
                "tool_profile": "test-only",
                "meaning": "No tool was actually executed",
            }
        )


def test_resume_cannot_be_a_boolean_without_checkpoint_and_approval():
    with pytest.raises(ValidationError, match="checkpoint and approval"):
        ControlCommand.model_validate(
            {
                "command_id": IDENTIFIER,
                "execution_id": IDENTIFIER,
                "action": "resume",
                "expected_revision": 1,
                "reason": "Test-only resume request",
            }
        )


def test_schema_contains_two_level_module_operation_discriminators():
    schema = deepcopy(RUN_ADAPTER.json_schema())
    mapping = schema["discriminator"]["mapping"]
    assert set(mapping) == {"discovery", "repair", "rules"}
    assert set(mapping["repair"]["discriminator"]["mapping"]) == {
        "generate",
        "build_suite",
        "verify",
    }


def test_remaining_operation_contracts_are_independently_validatable():
    scan = scan_spec()
    scout = {
        **scan,
        **model_fields(),
        "operation": "scout",
        "inputs": {
            "window_policy": {
                "version": "1",
                "max_windows": 2,
                "max_steps_per_window": 2,
                "max_calls": 4,
            },
        },
    }
    policy = {
        "version": "1",
        "batch_size": 4,
        "max_batches": 1,
        "supplement_insufficient": True,
        "max_steps": 3,
        "max_context_chars": 4000,
    }
    review = {
        **scan,
        **model_fields(),
        "operation": "review",
        "inputs": {
            "targets": {"artifact": ref("candidate_bundle")},
            "evidence": {"artifact": ref("evidence_bundle")},
            "source_execution_ids": [IDENTIFIER],
            "policy": policy,
        },
    }
    discover = {
        **scan,
        "operation": "discover",
        "inputs": {"scan": scan["inputs"], "required_branches": ["scan"]},
    }
    suite_build = {
        **repair_spec(),
        "operation": "build_suite",
        "inputs": {
            "targets": target_bundle(),
            "requested_behavior": ref("materials"),
            "runtime_profile": "test-only",
        },
    }
    entity = {
        "execution_id": IDENTIFIER,
        "entity_id": IDENTIFIER,
        "bundle": ref("candidate_bundle"),
    }
    suite = {
        "suite_id": IDENTIFIER,
        "definition": ref("suite"),
        "suite_hash": "0" * 64,
        "target_refs": [entity],
        "source": "human",
        "image_digest": "sha256:test-only",
    }
    verify = {
        **scan,
        "module": "repair",
        "operation": "verify",
        "inputs": {
            "repair": entity,
            "patch": ref("patch"),
            "patched_source": scan["source"],
            "suite": suite,
            "validation_plan": {"syntax": True, "before_after": True},
        },
    }
    approval = {
        "decision_id": IDENTIFIER,
        "action_id": IDENTIFIER,
        "actor": {"kind": "human", "id": "test-only"},
        "approved": True,
        "reason": "Reviewed the exact frozen fixture content",
        "subject_digest": "0" * 64,
        "created_at": "2026-11-10T18:00:00+08:00",
    }
    rule_validate = {
        **scan,
        "module": "rules",
        "operation": "validate",
        "inputs": {
            "rule": entity,
            "query": {
                "rule_id": IDENTIFIER,
                "version": "1",
                "purpose": "vulnerability_detector",
                "language": "python",
                "query": ref("query"),
                "dependencies": ref("dependencies"),
                "query_hash": "0" * 64,
            },
            "fixtures": ref("rule_fixtures"),
            "approval": approval,
        },
    }
    for value in (scout, review, discover, suite_build, verify, rule_validate):
        parsed = validate_spec(value)
        assert parsed.operation == value["operation"]
        assert validate_spec(parsed) == parsed
    resume = ControlCommand.model_validate(
        {
            "command_id": IDENTIFIER,
            "execution_id": IDENTIFIER,
            "action": "resume",
            "expected_revision": 1,
            "checkpoint_digest": "0" * 64,
            "approval": approval,
            "reason": "Resume the exact approved checkpoint",
        }
    )
    assert resume.approval.subject_digest == "0" * 64
