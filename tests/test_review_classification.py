"""Omitted taxonomy must preserve detector identity and dangerous-call validation."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from app.adapters.operation_evidence import locate_quote
from app.contracts.discovery_semantics import SemanticAssessment
from app.domain.audit import AuditError
from app.services.review_verdict_gate import validate_assessment

from tests.test_discovery_semantics import SemanticModel
from tests.test_dual_discovery import run_scout
from tests.test_unified_review import run_review


def test_omitted_model_cwe_retains_detector_taxonomy_and_explicit_history(
    pipeline_context,
):
    run_scout(pipeline_context)

    class Omitted(SemanticModel):
        def generate(self, purpose, payload, schema):
            response = super().generate(purpose, payload, schema)
            for assessment in response.candidate_assessments:
                assessment.weakness = "unknown"
            return response

    service = run_review(pipeline_context, Omitted(), version="8", discover=False)
    stage = service.repository.get(service.stage_id)
    classes = stage.result["batches"][0]["classifications"]
    assert len(classes) == 2
    original = next(c for c in classes if c["detector_weakness"] == "CWE-639")
    assert original["model_weakness"] == "unknown"
    assert original["effective_weakness"] == "CWE-639"
    assert all(
        r["weakness"] == "unknown" for r in stage.result["batches"][0]["assessments"]
    )
    from app.core.db import engine
    from app.persistence.stage_models import Candidate
    from sqlmodel import Session

    with Session(engine) as db:
        assert db.get(Candidate, original["candidate_id"]).weakness == "CWE-639"


def test_missing_model_cwe_cannot_bypass_original_injection_binding(monkeypatch):
    candidate_id, evidence_id = uuid4(), uuid4()
    target = {
        "candidate_id": str(candidate_id),
        "security_property": "input_injection",
        "required_premises": ["operation", "input_or_policy", "unsafe_protection"],
        "location": {"file": "app.py", "line": 1},
        "hypothesis": {"weakness": "CWE-95"},
    }
    code = {
        "id": str(evidence_id),
        "kind": "code",
        "reference": {"file": "app.py", "start_line": 1, "end_line": 1},
        "content": "rp(data)",
    }
    assessment = SemanticAssessment(
        candidate_id=candidate_id,
        assessment="supported",
        weakness="unknown",
        security_property="input_injection",
        reason="This operation would evaluate attacker input if its binding existed.",
        evidence_ids=[evidence_id],
        checked_premises=["Quoted operation checked."],
        premises=[
            {
                "premise": role,
                "status": "established",
                "reason": "The supplied source shows the proposed operation.",
                "evidence_ids": [evidence_id],
                "quote": "rp(data)",
            }
            for role in target["required_premises"]
        ],
    )
    monkeypatch.setattr(
        "app.adapters.python_bindings.location_bindings",
        lambda *_: [{"direct_calls": [{"binding": "no_static_binding"}]}],
    )
    assert (
        locate_quote(
            SimpleNamespace(
                primary_location=SimpleNamespace(file="app.py", line=1),
                operation_quote="rp(data)",
                evidence_ids=[evidence_id],
            ),
            {"snapshot": "s", "evidence": [code]},
            "python",
        )["line"]
        == 1
    )
    service = SimpleNamespace(
        stage=SimpleNamespace(prompt_version="8"),
        evidence=SimpleNamespace(audit=SimpleNamespace(language="python")),
    )
    with pytest.raises(AuditError, match="符号绑定"):
        validate_assessment(
            service,
            assessment,
            {"snapshot": "s", "language": "python", "evidence": [code]},
            {str(candidate_id): target},
            lambda *_: [code],
        )
