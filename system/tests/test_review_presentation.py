"""Candidate-local accepted verdicts and honest source-grounded example boundaries."""

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from app.contracts.review_presentation import ReviewDetail
from app.domain.audit import AuditError
from app.services.candidate_reviews import candidate_review
from app.services.review_presentation import validate_detail


def test_review_selects_only_accepted_assessment_for_own_candidate_and_snapshot():
    candidate = SimpleNamespace(
        id=uuid4(), stage_id=uuid4(), audit_id=uuid4(), evidence_ids=["linked"]
    )
    other = str(uuid4())
    stage = SimpleNamespace(
        id=candidate.stage_id,
        audit_id=candidate.audit_id,
        kind="review",
        status="completed",
        updated_at=datetime.now(timezone.utc),
        result={
            "snapshot_hash": "snapshot",
            "batches": [
                {
                    "assessments": [
                        {
                            "candidate_id": other,
                            "assessment": "supported",
                            "reason": "another candidate",
                        }
                    ]
                },
                {
                    "assessments": [
                        {
                            "candidate_id": str(candidate.id),
                            "assessment": "excluded",
                            "reason": "guard blocks path",
                            "counterevidence_ids": ["guard"],
                        }
                    ]
                },
            ],
        },
    )
    stages = {stage.id: stage}
    result = candidate_review(candidate, stages, "snapshot")
    assert result["status"] == "excluded" and result["evaluated"]
    assert result["reason"] == "guard blocks path"
    assert result["evidence_ids"] == ["linked", "guard"]
    assert candidate_review(candidate, stages, "another-snapshot") is None
    stage.audit_id = uuid4()
    assert candidate_review(candidate, stages, "snapshot") is None
    stage.audit_id = candidate.audit_id
    stage.result["batches"] = [{"status": "incomplete", "assessments": []}]
    result = candidate_review(candidate, stages, "snapshot")
    assert result["status"] == "insufficient" and not result["evaluated"]


def test_example_requires_actual_source_quote_and_cannot_claim_executed_success():
    identifier = uuid4()
    detail = ReviewDetail.model_validate(
        {
            "title": "候选请求输入处理问题",
            "description": "请求输入被传入实际项目中的敏感操作。",
            "impact": "满足所列前提后可能破坏项目的输入安全边界。",
            "evidence_ids": [str(identifier)],
            "exploitation": {
                "status": "illustrative",
                "entrypoint": "/demo",
                "steps": ["发送本地示例请求"],
                "example": "GET /demo?value=example",
                "expected_result": "预期输入到达实际敏感操作，尚未运行验证。",
                "source_quote": "def demo():",
                "evidence_ids": [str(identifier)],
            },
        }
    )
    assessment = SimpleNamespace(detail=detail, assessment="supported", evidence_ids=[])

    def evidence(ids):
        assert set(ids) <= {identifier}
        return [{"kind": "code", "content": "def demo():\n    return value"}]

    validate_detail(assessment, evidence)
    assert assessment.evidence_ids == [identifier]
    detail.exploitation.source_quote = "invented route"
    with pytest.raises(AuditError, match="实际入口"):
        validate_detail(assessment, evidence)
    detail.exploitation.source_quote = "def demo():"
    assessment.assessment = "insufficient"
    with pytest.raises(AuditError, match="未支持"):
        validate_detail(assessment, evidence)
    assert detail.exploitation.execution_status == "not_executed"
