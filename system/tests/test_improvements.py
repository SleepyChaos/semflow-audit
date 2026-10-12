"""Behavioral gates for recovery, benign assessment and independent rule semantics."""

import json
from uuid import UUID, uuid4

import httpx
import pytest
from app.adapters.ai.policy import CallBudget
from app.adapters.retrieval.chunking import semantic_chunks
from app.adapters.retrieval.knowledge import KnowledgeRetriever, import_knowledge
from app.contracts.review import ReviewResponseV2
from app.core.db import engine
from app.domain.audit import AuditError
from app.persistence.audit_models import AuditRun
from app.persistence.knowledge_models import RuleVersion
from app.persistence.stage_models import Candidate, StageRun
from app.persistence.stage_repository import StageRepository
from app.services.review import ReviewService
from app.services.rule_holdouts import (
    catalog,
    check_modern_validation,
    dataset,
    validation_fingerprint,
)
from sqlmodel import Session, select

from tests.test_model_provider import completion, configured


def test_length_recovery_preserves_failed_attempt_and_usage(monkeypatch):
    responses = [
        completion("{", "length"),
        completion('{"action":"final","summary":"unknown"}'),
    ]
    budgets = []

    def handler(request):
        budgets.append(json.loads(request.content)["max_tokens"])
        return httpx.Response(200, json=responses.pop(0))

    provider = configured(monkeypatch, handler)
    from app.contracts.stages import ReviewResponse

    provider.generate("review", {}, ReviewResponse)
    assert budgets[1] == 2 * budgets[0]
    assert provider.usage["calls"] == 2
    assert [r["error_code"] for r in provider.records] == ["length", None]
    assert provider.records[0]["response_model"] and provider.records[0]["seconds"] >= 0


def test_missing_usage_is_unknown_and_conservatively_budgeted(monkeypatch):
    reply = completion('{"action":"final"}')
    reply.pop("usage")
    provider = configured(monkeypatch, lambda _: httpx.Response(200, json=reply))
    from app.contracts.stages import ReviewResponse

    provider.generate("review", {}, ReviewResponse)
    assert provider.records[0]["input_tokens"] is None
    assert provider.usage["unknown_usage_calls"] == 1
    provider.policy["max_tokens"] = provider.records[0]["reserved_tokens"]
    with pytest.raises(AuditError, match="budget_exhausted"):
        provider.generate("review", {}, ReviewResponse)
    assert provider.usage["calls"] == 1


def test_schema_recovery_is_bounded(monkeypatch):
    provider = configured(
        monkeypatch, lambda _: httpx.Response(200, json=completion('{"extra":"bad"}'))
    )
    with pytest.raises(AuditError):
        provider.generate("review", {}, ReviewResponseV2)
    assert len(provider.records) == 2
    assert all(r["error_code"] == "schema_invalid" for r in provider.records)


def test_call_budget_blocks_before_provider():
    policy = {"max_calls": 1, "max_tokens": 100, "max_seconds": 10, "timeout": 5}
    with pytest.raises(AuditError):
        CallBudget(
            policy, [{"seconds": 0, "input_tokens": 10, "output_tokens": 1}]
        ).reserve(20)


def setup_review(ctx):
    with Session(engine) as db:
        audit = db.get(
            AuditRun,
            ctx["run_id"],
        )
        audit.findings = []
        db.add(audit)
        stage = StageRun(audit_id=ctx["run_id"], kind="review", prompt_version="2")
        db.add(stage)
        db.commit()
        db.refresh(stage)
        identifier = str(stage.id)
    StageRepository().claim(identifier)
    from tests.model_fixtures import ScriptedModel

    service = ReviewService(identifier, ScriptedModel())
    state = service.prepare()
    code = service.evidence.read("app.py", 1, 1)
    state["context"]["evidence"].append(code)
    return service, state, code


def test_benign_anchor_creates_no_candidate(pipeline_context):
    service, state, code = setup_review(pipeline_context)
    anchor = state["context"]["anchors"][0]["id"]
    state["response"] = {
        "action": "final",
        "anchor_assessments": [
            {
                "anchor_id": anchor,
                "weakness": "CWE-95",
                "assessment": "excluded",
                "reason": "Explicit test: anchor is benign for the assessed weakness.",
                "evidence_ids": [code["id"]],
            }
        ],
    }
    service.save(state)
    stage = StageRepository().get(service.stage_id)
    assert stage.result["anchor_assessments"][0]["assessment"] == "excluded"
    with Session(engine) as db:
        assert not db.exec(
            select(Candidate).where(Candidate.stage_id == UUID(service.stage_id))
        ).all()


def test_v2_save_is_atomic_and_rejects_invented_evidence(pipeline_context):
    service, state, code = setup_review(pipeline_context)
    anchor = state["context"]["anchors"][0]["id"]
    good = {
        "title": "Potential defect",
        "description": "Evidence-backed new test defect.",
        "primary_location": {"file": "app.py", "line": 1},
        "related_target": anchor,
        "evidence_ids": [code["id"]],
    }
    bad = {**good, "evidence_ids": [str(uuid4())]}
    state["response"] = {"action": "final", "new_findings": [good, bad]}
    with pytest.raises(AuditError, match="未取到"):
        service.save(state)
    with Session(engine) as db:
        assert not db.exec(
            select(Candidate).where(Candidate.stage_id == UUID(service.stage_id))
        ).all()


def test_unreviewed_anchor_is_explicit(pipeline_context):
    service, state, _ = setup_review(pipeline_context)
    state["response"] = {"action": "final", "summary": "No conclusion"}
    service.save(state)
    assert StageRepository().get(service.stage_id).result["unreviewed_anchor_ids"]


def test_semantic_chunks_preserve_fenced_api_examples():
    content = "# API one\n```ql\nselect 1\n# not a heading\n```\n# API two\nnotes"
    chunks = semantic_chunks(content)
    assert len(chunks) == 2 and chunks[0].count("```") == 2
    with pytest.raises(AuditError):
        semantic_chunks("```ql\nnot closed")


def test_version_filter_and_import_deduplication(pipeline_context):
    owner = pipeline_context["owner"]
    args = (
        owner,
        "Pinned API",
        "test-provenance",
        "python",
        "version_unique_probe fixed CodeQL API source content. ",
        {"api_version": "test-v1", "license": "test"},
    )
    first = import_knowledge(*args)
    second = import_knowledge(*args)
    assert first["document_id"] == second["document_id"]
    assert not KnowledgeRetriever().retrieve(
        owner, "python", "version_unique_probe", api_version="test-v2"
    )
    assert KnowledgeRetriever().retrieve(
        owner, "python", "version_unique_probe", api_version="test-v1"
    )


def test_independent_catalog_has_separate_purposes():
    assert len(catalog()) == 12
    anchor = dataset("python-eval-review_anchor-v1")
    detector = dataset("python-eval-vulnerability_detector-v1")
    assert (
        anchor["fixtures"] != detector["fixtures"]
        and anchor["hash"] != detector["hash"]
    )


def test_modern_rule_requires_independent_and_dependency_hash():
    rule = RuleVersion(
        owner_id=uuid4(),
        audit_id=uuid4(),
        stage_id=uuid4(),
        language="python",
        title="test",
        strategy="new_query",
        purpose="review_anchor",
        holdout_id="python-eval-review_anchor-v1",
        query="select 1",
        query_hash="unused",
    )
    rule.validation = {
        "validation_fingerprint": validation_fingerprint(rule),
        "independent_holdout": {
            "status": "passed",
            "dataset_hash": dataset(rule.holdout_id)["hash"],
        },
    }
    check_modern_validation(rule)
    rule.dependencies = {"codeql/python-all": {"version": "changed"}}
    with pytest.raises(AuditError, match="内容已变化"):
        check_modern_validation(rule)


@pytest.mark.parametrize("independent_status", ["passed", "failed"])
def test_rule_validation_persists_result_without_detached_session(
    pipeline_context, monkeypatch, independent_status
):
    from app.services import rules

    from tests.model_fixtures import ScriptedModel

    with Session(engine) as db:
        stage = StageRun(
            audit_id=pipeline_context["run_id"],
            kind="rule",
            prompt_version="2",
            inputs={"requirement": "Generate a test eval anchor query"},
        )
        db.add(stage)
        db.commit()
        db.refresh(stage)
        stage_id = str(stage.id)
        rule = RuleVersion(
            owner_id=pipeline_context["owner"],
            audit_id=pipeline_context["run_id"],
            stage_id=stage.id,
            language="python",
            title="query",
            strategy="new_query",
            purpose="review_anchor",
            query="select 1",
            query_hash="test",
            fixtures_approved=True,
        )
        db.add(rule)
        db.commit()
        db.refresh(rule)
        rule_id = str(rule.id)
    StageRepository().claim(stage_id)
    monkeypatch.setattr(rules, "prepare_query", lambda *args: None)
    monkeypatch.setattr(
        rules, "validate_fixtures", lambda *args: {"status": "passed", "tests": {}}
    )
    monkeypatch.setattr(
        rules,
        "evaluate_holdout",
        lambda *args: {"status": independent_status, "dataset_id": "test"},
    )
    flags = rules.RuleService(stage_id, ScriptedModel()).validate({"rule_id": rule_id})
    result = StageRepository().get(stage_id)
    assert (
        result.status == "completed"
        and result.result["validation"]["independent_holdout"]["status"]
        == independent_status
    )

    assert flags["validated"] == (independent_status == "passed")


def test_independent_fixture_sources_are_syntactically_valid():
    from app.adapters.syntax import check_syntax

    for entry in catalog():
        data = dataset(entry["id"])
        for fixture in data["fixtures"].values():
            for name, content in fixture["files"].items():
                check_syntax(name, content)


def test_new_api_uses_validated_semantic_versions_and_rejects_wrong_holdout(
    pipeline_context, monkeypatch
):
    from app.api.routes import stages

    monkeypatch.setattr(stages.execute_stage, "delay", lambda *args: None)
    api = pipeline_context["client"]
    identifier = pipeline_context["run_id"]
    response = api.post(f"/api/v1/audits/{identifier}/review", json={})
    assert response.status_code == 201 and response.json()["prompt_version"] == "9"
    scout = api.post(f"/api/v1/audits/{identifier}/scout", json={})
    assert scout.status_code == 201 and scout.json()["prompt_version"] == "7"
    holdouts = api.get("/api/v1/rules/holdouts")
    assert holdouts.status_code == 200 and len(holdouts.json()) == 12
    wrong = api.post(
        f"/api/v1/audits/{identifier}/rule",
        json={
            "requirement": "Generate a Python eval review anchor",
            "purpose": "review_anchor",
            "holdout_id": "javascript-eval-review_anchor-v1",
        },
    )
    assert wrong.status_code == 422


def test_thinking_is_explicit_not_sent_by_default(monkeypatch):
    from app.core.audit_config import audit_settings

    # Verify the unset protocol independently of the developer's local .env.
    monkeypatch.setattr(audit_settings, "AI_THINKING_MODE", "")
    packets = []
    provider = configured(
        monkeypatch,
        lambda request: (
            packets.append(json.loads(request.content))
            or httpx.Response(200, json=completion('{"action":"final"}'))
        ),
    )
    from app.contracts.stages import ReviewResponse

    provider.generate("review", {}, ReviewResponse)
    assert "thinking" not in packets[0]
    provider.policy["thinking_mode"] = "disabled"
    provider.generate("review", {}, ReviewResponse)
    assert packets[1]["thinking"] == {"type": "disabled"}


def test_import_api_cannot_claim_official_trust(pipeline_context):
    api = pipeline_context["client"]
    response = api.post(
        "/api/v1/knowledge/",
        json={
            "title": "User material",
            "source": "claimed official source",
            "language": "python",
            "content": "A user supplied CodeQL knowledge paragraph for trust validation.",
            "provenance": {
                "trust": "pinned_codeql_source",
                "api_version": "4.0.10",
                "verified": True,
            },
        },
    )
    assert response.status_code == 201
    rows = api.get("/api/v1/knowledge/").json()
    doc = next(
        row for row in rows if row["document_id"] == response.json()["document_id"]
    )
    assert (
        doc["provenance"]["trust"] == "user_supplied"
        and "verified" not in doc["provenance"]
    )
