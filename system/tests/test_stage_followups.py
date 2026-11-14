"""Transactional platform follow-ups never re-execute completed repair graphs."""

# Reused pytest fixtures are intentionally injected as function arguments.
# ruff: noqa: F811

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import UUID

import pytest
from app.application import repair_followups
from app.core.db import engine
from app.models import get_datetime_utc
from app.persistence.stage_models import RepairRecord, StageFollowup, StageRun
from app.persistence.stage_repository import StageRepository
from sqlmodel import Session, select

from tests.test_verification_lifecycle import comparison_context  # noqa: F401

pytestmark = pytest.mark.parametrize(
    "pipeline_context",
    [{"app.py": "def calculate(value):\n    return eval(value)\n"}],
    indirect=True,
)


def prepare(context):
    with Session(engine) as session:
        record = session.get(RepairRecord, UUID(context["repair_id"]))
        source = session.get(StageRun, record.stage_id)
        inputs = {**source.inputs, "verification_suite_id": context["suite_id"]}
        source_id = source.id
    StageRepository().update(
        str(source_id),
        status="completed",
        inputs=inputs,
        result={"repair_id": context["repair_id"]},
    )
    with Session(engine) as session:
        row = session.exec(
            select(StageFollowup).where(StageFollowup.source_stage_id == source_id)
        ).one()
        return source_id, row.id


def verification_rows(context):
    with Session(engine) as session:
        return list(
            session.exec(
                select(StageRun).where(
                    StageRun.audit_id == context["run_id"],
                    StageRun.kind == "verification",
                )
            ).all()
        )


def test_completion_commits_one_intent_without_queue_access(comparison_context):
    source_id, row_id = prepare(comparison_context)
    StageRepository().update(str(source_id), status="completed")
    assert verification_rows(comparison_context) == []
    with Session(engine) as session:
        row = session.get(StageFollowup, row_id)
        assert row.status == "pending" and row.attempts == 0
        assert (
            len(
                session.exec(
                    select(StageFollowup).where(
                        StageFollowup.source_stage_id == source_id
                    )
                ).all()
            )
            == 1
        )


def test_duplicate_runtime_delivery_never_replays_repair(
    comparison_context, monkeypatch
):
    from app.runtime import stages

    source_id, row_id = prepare(comparison_context)
    sent = []
    monkeypatch.setattr(
        "app.application.stage_dispatch.celery_publisher",
        lambda *args: sent.append(args),
    )
    monkeypatch.setattr(
        stages,
        "CompatibleModel",
        lambda: pytest.fail("Completed repair must not call a model"),
    )
    assert stages.run_stage(str(source_id)).status == "completed"
    assert stages.run_stage(str(source_id)).status == "completed"
    assert len(sent) == 1 and len(verification_rows(comparison_context)) == 1
    with Session(engine) as session:
        row = session.get(StageFollowup, row_id)
        assert row.status == "delivered" and str(row.target_stage_id) == sent[0][0]


def test_crash_after_target_commit_reuses_the_same_execution(comparison_context):
    source_id, row_id = prepare(comparison_context)
    _, attempt = repair_followups._claim(source_id)
    target = repair_followups._target(row_id, attempt)
    with Session(engine) as session:
        row = session.get(StageFollowup, row_id)
        row.target_stage_id = None  # Simulate losing the pointer after target commit.
        row.lease_until = get_datetime_utc() - timedelta(seconds=1)
        session.add(row)
        session.commit()
    sent = []
    assert (
        repair_followups.reconcile_followups(publisher=lambda *args: sent.append(args))
        == 1
    )
    assert sent == [(str(target.id), False)]
    assert len(verification_rows(comparison_context)) == 1


def test_busy_verification_defers_instead_of_losing_the_intent(comparison_context):
    source_id, row_id = prepare(comparison_context)
    with Session(engine) as session:
        busy = StageRun(audit_id=comparison_context["run_id"], kind="verification")
        session.add(busy)
        session.commit()
        busy_id = busy.id
    assert (
        repair_followups.deliver_repair_followup(source_id, publisher=lambda *_: None)
        is None
    )
    with Session(engine) as session:
        assert session.get(StageFollowup, row_id).status == "pending"
        busy = session.get(StageRun, busy_id)
        busy.status = "completed"
        session.add(busy)
        session.commit()
    sent = []
    assert (
        repair_followups.reconcile_followups(publisher=lambda *args: sent.append(args))
        == 1
    )
    assert len(sent) == 1


def test_stale_lease_cannot_create_an_extra_failure_record(comparison_context):
    source_id, row_id = prepare(comparison_context)
    _, old_attempt = repair_followups._claim(source_id)
    with Session(engine) as session:
        row = session.get(StageFollowup, row_id)
        row.attempts += 1
        session.add(row)
        session.commit()
    assert repair_followups._failure(row_id, old_attempt) is None
    assert verification_rows(comparison_context) == []
    assert StageRepository().get(str(source_id)).status == "completed"


def test_transport_error_cannot_fail_an_already_claimed_task(comparison_context):
    source_id, row_id = prepare(comparison_context)

    def claim_then_lose_ack(identifier, _resume):
        assert StageRepository().claim(identifier)
        raise ConnectionError("Synthetic lost delivery acknowledgement")

    target = repair_followups.deliver_repair_followup(
        source_id, publisher=claim_then_lose_ack
    )
    assert target.status == "running"
    with Session(engine) as session:
        assert session.get(StageFollowup, row_id).status == "delivered"


def test_concurrent_deliveries_share_one_target(comparison_context):
    source_id, _ = prepare(comparison_context)
    sent = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda _: repair_followups.deliver_repair_followup(
                    source_id, publisher=lambda *args: sent.append(args)
                ),
                range(2),
            )
        )
    assert sum(result is not None for result in results) == 1
    assert len(sent) == 1 and len(verification_rows(comparison_context)) == 1


def test_target_commit_exception_is_recoverable_without_duplicate(
    comparison_context, monkeypatch
):
    source_id, row_id = prepare(comparison_context)
    original = repair_followups.create_stage_run

    def commit_then_crash(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("Synthetic crash after committing the target")

    monkeypatch.setattr(repair_followups, "create_stage_run", commit_then_crash)
    queued = repair_followups.deliver_repair_followup(
        source_id, publisher=lambda *_: None
    )
    assert queued.status == "queued"
    with Session(engine) as session:
        assert session.get(StageFollowup, row_id).status == "pending"
    monkeypatch.setattr(repair_followups, "create_stage_run", original)
    sent = []
    recovered = repair_followups.deliver_repair_followup(
        source_id, publisher=lambda *args: sent.append(args)
    )
    assert recovered.id == queued.id and len(sent) == 1
    assert len(verification_rows(comparison_context)) == 1
