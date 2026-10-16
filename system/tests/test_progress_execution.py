"""Full-scope execution, interruption receipts, old policy isolation and evidence gates."""

from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from app.adapters.ai.policy import CallBudget, policy_snapshot, stalled
from app.adapters.source_inventory import category, priority
from app.contracts.discovery_semantics import PremiseCheck
from app.core.audit_config import audit_settings
from app.core.db import engine
from app.domain.audit import AuditError
from app.persistence.audit_models import AuditRun
from app.persistence.stage_models import StageRun
from app.persistence.stage_repository import StageRepository
from app.services.discovery_context import validate_premises
from sqlmodel import Session

from tests.test_dual_discovery import HypothesisModel, run_scout
from tests.test_model_provider import completion, configured
from tests.test_unified_review import ReviewModel, run_review


def progress_policy():
    return {
        "execution_mode": "progress",
        "max_no_progress": 3,
        "max_calls": 0,
        "max_tokens": 0,
        "max_seconds": 0,
        "timeout": 90,
    }


def test_progress_keeps_accounting_without_byte_reservation_stop(monkeypatch):
    monkeypatch.setattr(audit_settings, "AI_AUDIT_EXECUTION_MODE", "progress")
    policy = policy_snapshot("review")
    assert policy["max_calls"] == policy["max_tokens"] == policy["max_seconds"] == 0
    records = [
        {"input_tokens": 47311, "output_tokens": 9255, "seconds": 59},
        {"input_tokens": None, "output_tokens": None, "reserved_tokens": 90000},
    ] * 20
    assert CallBudget(policy, records).reserve(6000, 60000) == policy["timeout"]
    bounded = {**policy, "max_tokens": 100000}
    with pytest.raises(AuditError, match="tokens="):
        CallBudget(bounded, records).reserve(6000, 60000)
    assert policy_snapshot("repair")["max_calls"] == 0
    assert policy_snapshot("rule")["max_calls"] > 0
    monkeypatch.setattr(audit_settings, "AI_AUDIT_EXECUTION_MODE", "bounded")
    assert policy_snapshot("repair")["max_calls"] > 0


def test_bounded_execution_can_be_restored(monkeypatch):
    monkeypatch.setattr(audit_settings, "AI_AUDIT_EXECUTION_MODE", "bounded")
    policy = policy_snapshot("scout")
    assert policy["execution_mode"] == "bounded" and policy["max_calls"] > 0


@pytest.mark.parametrize(
    "pipeline_context",
    [{f"module{i:02}.py": "value = 1\n" for i in range(30)}],
    indirect=True,
)
def test_scout_covers_more_than_24_windows_with_real_persisted_evidence(
    pipeline_context,
):
    model = HypothesisModel()
    model.policy = progress_policy()
    service = run_scout(pipeline_context, model, version="4")
    result = service.repository.get(service.stage_id).result
    assert result["coverage"]["inspected_windows"] == 30
    assert result["coverage"]["uninspected_windows"] == 0
    assert model.usage["calls"] == 30
    assert len({p["unit"]["id"] for p in model.seen}) == 30
    assert all(u["hypotheses"][0]["evidence_ids"] for u in result["units"])


@pytest.mark.parametrize(
    "pipeline_context",
    [{f"module{i:02}.py": "value = 1\n" for i in range(30)}],
    indirect=True,
)
def test_no_progress_stops_without_erasing_unchecked_windows(pipeline_context):
    class Broken(HypothesisModel):
        def generate(self, *args):
            self.usage["calls"] += 1
            raise AuditError("Fixture: malformed response", code="schema_invalid")

    model = Broken()
    model.policy = progress_policy()
    service = run_scout(pipeline_context, model, version="4")
    coverage = service.repository.get(service.stage_id).result["coverage"]
    assert model.usage["calls"] == 3
    assert coverage["stop_reason"] == "no_progress"
    assert coverage["status"] == "partial" and coverage["uninspected_windows"] == 30


def test_successful_work_resets_no_progress_streak():
    failed = {"status": "incomplete"}
    partial = {"status": "partial", "recommendations": []}
    assert stalled([failed, partial, failed], progress_policy())
    assert not stalled([failed, {"status": "inspected"}, failed], progress_policy())
    assert not stalled([failed] * 3, {"execution_mode": "bounded"})


def test_review_schedules_more_than_24_batches(pipeline_context):
    with Session(engine) as db:
        audit = db.get(AuditRun, pipeline_context["run_id"])
        base = audit.findings[0]
        audit.findings = [{**base, "id": f"alert-{i}"} for i in range(30)]
        db.add(audit)
        db.commit()
    model = ReviewModel()
    model.policy = progress_policy()
    service = run_review(pipeline_context, model, batch_size=1, include_scout=False)
    result = service.repository.get(service.stage_id).result
    assert result["schedule"]["scheduled_batches"] == 30
    assert len(result["recommendations"]) == 30
    assert not result["unreviewed_candidate_ids"]


def test_rate_limit_records_interruption_without_retrying_paid_calls(monkeypatch):
    provider = configured(
        monkeypatch,
        lambda _: httpx.Response(
            429,
            headers={"retry-after": "18000"},
            json={"error": {"message": "plan limit", "type": "rate_limit_error"}},
        ),
    )
    from app.contracts.stages import ReviewResponse

    with pytest.raises(AuditError) as failure:
        provider.generate("review", {}, ReviewResponse)
    assert failure.value.code == "rate_limited"
    assert provider.usage["calls"] == 1
    assert provider.records[0]["retry_after"] == "18000"
    assert provider.usage["unknown_usage_calls"] == 1


def test_existing_stage_keeps_bounded_policy(pipeline_context, monkeypatch):
    provider = configured(
        monkeypatch,
        lambda _: httpx.Response(
            200,
            json=completion('{"action":"final"}'),
        ),
    )
    old = {**provider.policy, "max_calls": 2, "max_tokens": 100000, "max_seconds": 300}
    with Session(engine) as db:
        stage = StageRun(
            audit_id=pipeline_context["run_id"],
            kind="review",
            prompt_version="1",
            model_config_snapshot=old,
        )
        db.add(stage)
        db.commit()
        db.refresh(stage)
        identifier = str(stage.id)
    StageRepository().claim(identifier)
    provider.bind_stage(identifier, "1")
    assert provider.policy["max_calls"] == 2 and "execution_mode" not in provider.policy


def test_debug_config_accepts_inapplicable_input_but_requires_operation_quote():
    source_id = uuid4()
    target = {
        "security_property": "secrets_config",
        "required_premises": ["operation", "input_or_policy", "unsafe_protection"],
    }
    assessment = SimpleNamespace(
        security_property="secrets_config",
        assessment="supported",
        premises=[
            PremiseCheck(
                premise=role,
                status="not_applicable" if role == "input_or_policy" else "established",
                reason="Literal debug configuration does not require attacker-controlled input.",
                evidence_ids=[] if role == "input_or_policy" else [source_id],
                quote="" if role == "input_or_policy" else "app.run(debug=True)",
            )
            for role in target["required_premises"]
        ],
    )
    rows = [
        {
            "id": str(source_id),
            "kind": "code",
            "reference": {"file": "app.py"},
            "content": "app.run(debug=True)",
        }
    ]
    validate = lambda: validate_premises(
        assessment,
        target,
        {"language": "python"},
        lambda ids: [r for r in rows if r["id"] in set(map(str, ids))],
    )
    validate()
    assessment.premises[0].quote = "app.run(debug=False)"
    with pytest.raises(AuditError, match="源码引用"):
        validate()
    assessment.premises[0].status = "not_applicable"
    with pytest.raises(AuditError, match="仅配置缺陷"):
        validate()


def test_migrations_do_not_outrank_runtime_views():
    assert category("introduction/views.py") == "entrypoint"
    assert category("introduction/migrations/0010_authlogin.py") == "migration"
    assert priority("introduction/views.py") < priority(
        "introduction/migrations/0010_authlogin.py"
    )


@pytest.mark.parametrize(
    "pipeline_context",
    [
        {
            "introduction/views.py": "def login(request):\n    return request.POST\n",
            "introduction/migrations/0010_authlogin.py": "class Migration:\n    pass\n",
        }
    ],
    indirect=True,
)
def test_runtime_window_precedes_migration_without_hiding_gap(pipeline_context):
    model = HypothesisModel()
    model.policy = progress_policy()
    service = run_scout(pipeline_context, model, version="4", max_units=1)
    coverage = service.repository.get(service.stage_id).result["coverage"]
    assert model.seen[0]["unit"]["file"] == "introduction/views.py"
    assert coverage["uninspected_windows"] == 1 and coverage["status"] == "partial"
    assert any(
        f["file"].endswith("0010_authlogin.py") and f["inspected_windows"] == 0
        for f in coverage["files"]
    )


def test_audit_worker_does_not_inherit_pool_wallclock_kill():
    from app.jobs.celery_app import celery_app
    from app.jobs.scan import execute_scan
    from app.jobs.stages import execute_stage

    assert celery_app.conf.task_time_limit is None
    assert execute_stage.time_limit == execute_scan.time_limit == 0
    assert celery_app.conf.task_annotations["audit.knowledge_index"]["time_limit"] > 0


def test_distinct_evidence_rejections_do_not_stop_other_candidates():
    rows = [
        {
            "status": "partial",
            "recommendations": [],
            "rejected_assessments": [
                {"candidate_id": str(i), "reason": "Local control proof missing"}
            ],
        }
        for i in range(3)
    ]
    assert not stalled(rows, progress_policy())
    assert stalled(
        [{"status": "partial", "recommendations": []}] * 3, progress_policy()
    )
    assert stalled(
        [{"status": "incomplete", "code": "schema_invalid"}] * 3, progress_policy()
    )
