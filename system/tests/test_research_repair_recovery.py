"""Real worker/bridge/graph/projection with only external model and tool substitutes."""

import shutil
from uuid import UUID

import pytest
from app.adapters.artifacts import ArtifactStore
from app.core.audit_config import audit_settings
from app.domain.audit import AuditError
from app.persistence.audit_models import AuditRun
from app.persistence.stage_models import (
    Candidate,
    Decision,
    Evidence,
    RepairRecord,
    StageRun,
)
from app.research_bridge import repair_runtime
from app.research_bridge.models import ResearchBinding
from app.research_bridge.requests import research_root
from app.runtime.stages import run_stage
from app.services.repair_integrity import verify_acceptance
from semflow_research.public.runs import inspect
from sqlmodel import Session, select

from tests.research_repair_cases import create_confirmed_repair


def rows(case, stage_id):
    with Session(case[0]) as session:
        stage = session.get(StageRun, stage_id)
        binding = session.exec(
            select(ResearchBinding).where(ResearchBinding.stage_id == stage_id)
        ).one()
        record = session.exec(
            select(RepairRecord).where(RepairRecord.stage_id == stage_id)
        ).first()
        session.expunge_all()
        return stage, binding, record


def forbidden(*args, **kwargs):
    raise AssertionError("Recovery must not create a provider, graph or validator")


def test_redelivery_rebuilds_deleted_views_without_model_and_preserves_acceptance(
    bridge_case, scanner, repair_model, syntax, monkeypatch
):
    stage_id = create_confirmed_repair(bridge_case)
    assert run_stage(str(stage_id)).status == "completed"
    stage, binding, record = rows(bridge_case, stage_id)
    result = inspect(binding.execution_id, root=research_root())
    assert record.id != result.result.repair_id
    assert record.candidate_ids == stage.inputs["candidate_ids"]
    assert not set(
        map(str, (r.entity_id for r in result.result.target_refs))
    ).intersection(record.candidate_ids)
    assert stage.usage["calls"] == 3
    assert record.validation["syntax"]["status"] == "passed"
    assert record.validation["isolated_tests"]["status"] == "not_run"
    with Session(bridge_case[0]) as session:
        verify_acceptance(record, session.get(AuditRun, stage.audit_id))
        saved = session.get(RepairRecord, record.id)
        saved.status, saved.accepted_by, saved.acceptance_reason = (
            "accepted",
            bridge_case[1],
            "Existing human acceptance must be preserved",
        )
        session.add(saved)
        session.commit()
    shutil.rmtree(research_root() / "workspaces" / str(binding.execution_id))
    directory = ArtifactStore().directory(str(stage_id))
    shutil.rmtree(directory)
    monkeypatch.setattr(repair_runtime, "prepare", forbidden)
    assert run_stage(str(stage_id)).status == "completed"
    assert run_stage(str(stage_id)).status == "completed"
    assert (directory / "workspace/app.py").read_text() == "value = int(input())\n"
    assert (directory / "repair.diff").is_file()
    _, rebound, saved = rows(bridge_case, stage_id)
    assert saved.status == "accepted" and saved.accepted_by == bridge_case[1]
    assert saved.acceptance_reason == "Existing human acceptance must be preserved"
    assert rebound.manifest == binding.manifest
    assert len(repair_model) == 3 and len(syntax) == 1


def test_projection_crash_recovers_published_result_without_regeneration(
    bridge_case, scanner, repair_model, syntax, monkeypatch
):
    stage_id = create_confirmed_repair(bridge_case)
    commit = Session.commit
    failed = []

    def crash_on_projection_commit(session):
        if not failed and any(
            isinstance(row, ResearchBinding) and row.manifest is not None
            for row in (*session.new, *session.dirty)
        ):
            failed.append(True)
            raise RuntimeError(
                "injected outage after materialization before projection commit"
            )
        return commit(session)

    monkeypatch.setattr(Session, "commit", crash_on_projection_commit)
    assert run_stage(str(stage_id)).status == "failed"
    _, binding, record = rows(bridge_case, stage_id)
    assert record is None and binding.manifest is None
    receipt = inspect(binding.execution_id, root=research_root())
    assert receipt.execution_status == "completed"
    shutil.rmtree(research_root() / "workspaces" / str(binding.execution_id))
    assert (
        failed and (ArtifactStore().directory(str(stage_id)) / "repair.diff").is_file()
    )
    monkeypatch.setattr(Session, "commit", commit)
    monkeypatch.setattr(repair_runtime, "prepare", forbidden)
    assert run_stage(str(stage_id)).status == "completed"
    assert inspect(binding.execution_id, root=research_root()) == receipt
    assert rows(bridge_case, stage_id)[2] is not None
    assert len(repair_model) == 3 and len(syntax) == 1


@pytest.mark.parametrize("cancel", [False, True])
def test_outputless_failure_and_cancellation_keep_receipts_and_no_repair_record(
    bridge_case, scanner, repair_model, syntax, monkeypatch, cancel
):
    from semflow_research.adapters.ai import provider

    stage_id = create_confirmed_repair(bridge_case)
    factory = provider.OpenAI

    def client(**kwargs):
        value = factory(**kwargs)

        def create(**kwargs):
            if cancel:
                with Session(bridge_case[0]) as session:
                    current = session.get(StageRun, stage_id)
                    current.status = "cancelled"
                    session.add(current)
                    session.commit()
                return value.original(**kwargs)
            raise RuntimeError("injected external model failure")

        value.original = value.chat.completions.create
        value.chat.completions.create = create
        return value

    monkeypatch.setattr(provider, "OpenAI", client)
    stage = run_stage(str(stage_id))
    expected = "cancelled" if cancel else "failed"
    assert stage.status == expected, stage.error
    _, binding, record = rows(bridge_case, stage_id)
    receipt = inspect(binding.execution_id, root=research_root())
    assert receipt.execution_status == expected and receipt.result is None
    assert receipt.failure is not None and binding.manifest is not None
    assert record is None and not syntax
    monkeypatch.setattr(repair_runtime, "prepare", forbidden)
    assert run_stage(str(stage_id)).status == expected


def test_frozen_resources_survive_live_config_change_and_secret_is_injected(
    bridge_case, scanner, repair_model, syntax, monkeypatch
):
    from pydantic import SecretStr
    from semflow_research.adapters.ai import provider

    stage_id = create_confirmed_repair(bridge_case)
    with Session(bridge_case[0]) as session:
        stage = session.get(StageRun, stage_id)
        binding = session.exec(
            select(ResearchBinding).where(ResearchBinding.stage_id == stage_id)
        ).one()
        repair_runtime.freeze_repair(
            binding, stage, session.get(AuditRun, stage.audit_id), session
        )
        original = dict(binding.resources)
        session.add(binding)
        session.commit()
    monkeypatch.setattr(audit_settings, "AI_BASE_URL", "http://changed.invalid")
    monkeypatch.setattr(audit_settings, "AI_MODEL", "must-not-use-live-model")
    monkeypatch.setattr(
        audit_settings, "AI_API_KEY", SecretStr("injected-test-only-secret")
    )
    monkeypatch.setattr(audit_settings, "SEMANTIC_TOOL_LIMIT", 999)
    monkeypatch.setattr(audit_settings, "VALIDATOR_TIMEOUT", 999)
    factory = provider.OpenAI

    def client(**kwargs):
        assert kwargs["base_url"] == original["AI_BASE_URL"]
        assert kwargs["api_key"] == "injected-test-only-secret"
        return factory(**kwargs)

    monkeypatch.setattr(provider, "OpenAI", client)
    assert run_stage(str(stage_id)).status == "completed"
    _, binding, record = rows(bridge_case, stage_id)
    assert binding.resources == original
    assert "injected-test-only-secret" not in str(binding.model_dump())
    assert record is not None


@pytest.mark.parametrize(
    "changed", ["decision", "evidence", "source", "fingerprint", "prompt"]
)
def test_changed_authorization_or_frozen_identity_never_calls_model(
    bridge_case, scanner, repair_model, syntax, changed
):
    stage_id = create_confirmed_repair(bridge_case)
    with Session(bridge_case[0]) as session:
        stage = session.get(StageRun, stage_id)
        candidate = session.get(Candidate, UUID(stage.inputs["candidate_ids"][0]))
        if changed == "decision":
            session.add(
                Decision(
                    candidate_id=candidate.id,
                    actor_id=bridge_case[1],
                    status="excluded",
                    reason="Latest operator decision revokes repair authorization",
                    evidence_ids=candidate.evidence_ids,
                )
            )
        elif changed == "evidence":
            row = session.get(Evidence, UUID(candidate.evidence_ids[0]))
            row.digest = "0" * 64
            session.add(row)
        elif changed == "source":
            audit = session.get(AuditRun, stage.audit_id)
            (ArtifactStore().source(str(audit.source_run_id)) / "app.py").write_text(
                "changed\n"
            )
        elif changed == "prompt":
            stage.model_config_snapshot = {
                **stage.model_config_snapshot,
                "prompt_snapshot": {
                    **stage.model_config_snapshot["prompt_snapshot"],
                    "content": "changed",
                },
            }
            session.add(stage)
        else:
            binding = session.exec(
                select(ResearchBinding).where(ResearchBinding.stage_id == stage_id)
            ).one()
            repair_runtime.freeze_repair(
                binding, stage, session.get(AuditRun, stage.audit_id), session
            )
            binding.request = {
                **binding.request,
                "implementation": {
                    **binding.request["implementation"],
                    "code_digest": "0" * 64,
                },
            }
            session.add(binding)
        session.commit()
    stage = run_stage(str(stage_id))
    assert stage.status == "failed"
    assert not repair_model and not syntax
    assert rows(bridge_case, stage_id)[2] is None


def test_acceptance_verifies_immutable_projection_and_refuses_syntax_only(
    bridge_case, scanner, repair_model, syntax
):
    from app.main import app
    from fastapi.testclient import TestClient

    stage_id = create_confirmed_repair(bridge_case)
    assert run_stage(str(stage_id)).status == "completed"
    stage, _, record = rows(bridge_case, stage_id)
    with TestClient(app) as client:
        listing = client.get(f"/api/v1/audits/{stage.audit_id}/repairs")
        assert listing.status_code == 200, listing.text
        assert listing.json()[0]["candidate_ids"] == stage.inputs["candidate_ids"]
        assert listing.json()[0]["acceptance_ready"] is False
        assert client.get(f"/api/v1/stages/{stage_id}/materials").status_code == 200
        response = client.post(
            f"/api/v1/repairs/{record.id}/accept",
            json={
                "reason": "Syntax only must not count as acceptance",
                "test_reviewed": True,
                "comparison_stage_id": str(stage_id),
            },
        )
        assert response.status_code == 409, response.text
    directory = ArtifactStore().directory(str(stage_id))
    (directory / "repair.diff").write_text("modified")
    with (
        Session(bridge_case[0]) as session,
        pytest.raises(AuditError, match="presentation"),
    ):
        verify_acceptance(record, session.get(AuditRun, stage.audit_id))
