"""Explicit external model/validator substitutes shared by kernel and bridge tests."""

import ast
import json
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from openai.types.chat import ChatCompletion
from semflow_contracts.bundles import CandidateBundle, DecisionBundle, EvidenceBundle
from semflow_contracts.common import EntityRef, canonical_bytes
from semflow_contracts.discovery import CandidateRecord
from semflow_contracts.evidence import DecisionRecord
from semflow_contracts.runs import validate_spec


@pytest.fixture
def repair_model(monkeypatch):
    phases = []

    def create(**kwargs):
        payload = json.loads(kwargs["messages"][-1]["content"])[
            "untrusted_analysis_material"
        ]
        phase = payload["phase"]
        phases.append(phase)
        if phase == "inspect_semantics":
            source = next(row for row in payload["evidence"] if row["kind"] == "code")
            body = {
                "action": "ready",
                "project_overview": "The source reads and converts external input",
                "target_flow": "Input reaches eval and the computed value is stored",
                "modification_semantics": "Use integer conversion without dynamic interpretation",
                "facts": [
                    {
                        "statement": "The exact source uses eval on external input",
                        "state": "supported",
                        "evidence_ids": [source["id"]],
                        "category": "security",
                        "critical": True,
                    }
                ],
            }
        elif phase == "diagnose_failure":
            body = {
                "category": "inconclusive",
                "summary": "The external check remains unresolved; scripted model cannot establish remediation",
                "next_action": "Review the actual retained check evidence",
            }
        elif phase == "assess_patch_contract":
            body = {
                "constraints": [
                    {
                        "fact_index": index,
                        "status": "consistent",
                        "explanation": "The candidate replaces evaluation with bounded conversion",
                        "evidence_ids": [payload["evidence"][0]["id"]],
                    }
                    for index in payload["required_fact_indices"]
                ],
                "callers": [],
                "limitation": "Scripted model consistency is not an executed exploitation test",
            }
        else:
            assert phase == "propose_patch", phase
            body = {
                "changes": [
                    {
                        "file": "app.py",
                        "old_text": "eval(input())",
                        "new_text": "int(input())",
                        "reason": "Replace dynamic evaluation with explicit integer parsing",
                    }
                ],
                "summary": "Use explicit integer conversion while preserving the selected numeric intent",
            }
        return ChatCompletion(
            id="scripted",
            created=0,
            model="scripted",
            object="chat.completion",
            choices=[
                {
                    "index": 0,
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": json.dumps(body)},
                }
            ],
            usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        )

    monkeypatch.setattr(
        "semflow_research.adapters.ai.provider.OpenAI",
        lambda **kwargs: SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create)),
            base_url="http://scripted.invalid/v1",
        ),
    )
    return phases


@pytest.fixture
def syntax(monkeypatch):
    observed = []

    def validate(workspace, language, profile, *, _kernel):
        assert language == "python" and profile == "syntax"
        text = (workspace / "app.py").read_text()
        ast.parse(text)
        observed.append(text)
        return {
            "status": "passed",
            "profile": "syntax",
            "output": "Scripted validator boundary; actual Python AST parsed",
            "executor": "test-fixture",
        }

    monkeypatch.setattr("semflow_research.repair.repair.validate_workspace", validate)
    return observed


def repair_spec(case, *, confirmed=True, consistency=True):
    evidence = case.reader.read("app.py", 1, 1)
    evidence_ref = case.artifacts.commit(
        canonical_bytes(
            EvidenceBundle(
                execution_id=case.execution_id,
                snapshot_id=case.snapshot.snapshot_id,
                records=(evidence,),
            )
        ),
        kind="evidence_bundle",
        schema_version="semflow.research.bundle/1",
    )
    evidence_entity = EntityRef(
        execution_id=case.execution_id,
        entity_id=evidence.evidence_id,
        bundle=evidence_ref,
    )
    candidate = CandidateRecord(
        candidate_id=uuid4(),
        execution_id=case.execution_id,
        origin="scout",
        title="Input reaches eval",
        description="The source dynamically evaluates a value read from input",
        weakness="CWE-95",
        primary_location=evidence.location,
        identity_key="source-eval-hypothesis",
        novelty="unknown",
        evidence_refs=(evidence_entity,),
    )
    candidate_ref = case.artifacts.commit(
        canonical_bytes(
            CandidateBundle(
                execution_id=case.execution_id,
                snapshot_id=case.snapshot.snapshot_id,
                records=(candidate,),
            )
        ),
        kind="candidate_bundle",
        schema_version="semflow.research.bundle/1",
    )
    target = EntityRef(
        execution_id=case.execution_id,
        entity_id=candidate.candidate_id,
        bundle=candidate_ref,
    )
    decisions = (
        (
            DecisionRecord(
                decision_id=uuid4(),
                target=target,
                snapshot_id=case.snapshot.snapshot_id,
                status="confirmed",
                actor={"kind": "human", "id": "test-operator"},
                reason="Explicit operator selected the exact source evidence",
                evidence_refs=(evidence_entity,),
                created_at=datetime.now(UTC),
            ),
        )
        if confirmed
        else ()
    )
    decision_ref = case.artifacts.commit(
        canonical_bytes(
            DecisionBundle(
                execution_id=case.execution_id,
                snapshot_id=case.snapshot.snapshot_id,
                records=decisions,
            )
        ),
        kind="decision_bundle",
        schema_version="semflow.research.bundle/1",
    )
    prompt = case.artifacts.commit(
        b"Scripted repair: inspect actual source, propose a patch, then check consistency.",
        kind="prompt",
        schema_version="prompt/1",
    )
    value = case.spec.model_dump(mode="json")
    value.update(
        execution_id=str(uuid4()),
        module="repair",
        operation="generate",
        model={
            "provider": "scripted-test",
            "model": "scripted",
            "endpoint_profile": "scripted",
            "output_schema_version": "1",
            "output_tokens": 4000,
        },
        prompts=[
            {
                "role": "repair",
                "template_id": "repair",
                "version": "4",
                "content": prompt.model_dump(mode="json"),
                "sha256": prompt.sha256,
            }
        ],
        inputs={
            "engine": "native",
            "targets": {
                "snapshot_id": str(case.snapshot.snapshot_id),
                "candidates": {"artifact": candidate_ref.model_dump(mode="json")},
                "evidence": {"artifact": evidence_ref.model_dump(mode="json")},
                "decisions": {"artifact": decision_ref.model_dump(mode="json")},
            },
            "patch_scope": {
                "writable_paths": ["app.py"],
                "readable_paths": [],
                "max_changed_files": 1,
            },
            "validation_plan": {"syntax": True, "before_after": False},
            "method_policy": {
                "version": "1",
                "max_candidates": 1,
                "inspection_limits": {
                    "max_steps": 3,
                    "max_context_chars": 40000,
                    "max_expanded_context_chars": 80000,
                },
                "feedback_policy": {
                    "version": "1",
                    "semantic_consistency": consistency,
                    "refresh_understanding": True,
                    "stop_on_environment_error": True,
                },
                "selected_suite_feedback": False,
                "baseline_reuse": False,
            },
        },
    )
    value["implementation"]["method_version"] = "4"
    value["policy"].update(
        max_calls=8, max_tokens=300000, max_seconds=60, max_context_chars=40000
    )
    return validate_spec(value)
