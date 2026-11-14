"""Direct failure/recovery/authorization evidence for the shared native Web workflow."""

import ast
from uuid import UUID, uuid4

import pytest
from app.adapters.artifacts import ArtifactStore
from app.api.deps import get_workspace
from app.main import app
from app.persistence.audit_models import AuditRun
from app.persistence.stage_models import RepairRecord, StageRun
from app.persistence.workspace import Workspace
from app.research_bridge.models import ResearchBinding
from app.research_bridge.requests import research_root
from app.runtime.stages import run_stage
from fastapi.testclient import TestClient
from semflow_research.adapters.repair.verification_runner import parse_results
from semflow_research.public.runs import inspect
from semflow_research.runtime import repair_verify
from sqlmodel import Session, select

from tests.research_verification_cases import repair_ready, suite_ready


@pytest.mark.parametrize("change", ["assertions", "other_audit", "owner"])
def test_changed_or_unowned_suite_cannot_enter_repair(
    bridge_case,
    scanner,
    suite_model,
    repair_model,
    syntax,
    suite_runner,
    monkeypatch,
    change,
):
    setup = suite_ready(bridge_case, monkeypatch, suite_model)
    if change == "assertions":
        (
            ArtifactStore().directory(str(setup.suite_id)) / "tests/test_numeric.py"
        ).write_text("assert True\n")
    elif change == "other_audit":
        with Session(bridge_case[0]) as session:
            source = session.get(AuditRun, setup.audit_id)
            other = AuditRun(
                owner_id=bridge_case[1],
                source_run_id=source.source_run_id,
                project_name="other task",
                language="python",
                snapshot_hash=source.snapshot_hash,
                query_pack=source.query_pack,
                suite=source.suite,
                status="completed",
            )
            session.add(other)
            foreign = StageRun(
                audit_id=other.id, kind="verification_suite", status="completed"
            )
            session.add(foreign)
            session.commit()
            session.refresh(foreign)
            setup.suite_id = foreign.id
    else:
        app.dependency_overrides[get_workspace] = lambda: Workspace(uuid4())
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/audits/{setup.audit_id}/repair",
            json={
                "candidate_ids": setup.candidates,
                "allowed_paths": [],
                "validation_profile": "syntax",
                "rescan": True,
                "verification_suite_id": str(setup.suite_id),
            },
        )
        assert response.status_code in {404, 409}, response.text
    assert not repair_model and not syntax and not suite_runner


@pytest.mark.parametrize("mode", ["assertion_failure", "tool_failure", "cancel"])
def test_independent_comparison_failures_never_accept_or_rewrite_repair(
    bridge_case,
    scanner,
    suite_model,
    repair_model,
    syntax,
    suite_runner,
    monkeypatch,
    mode,
):
    setup = suite_ready(bridge_case, monkeypatch, suite_model)
    repair = repair_ready(bridge_case, monkeypatch, setup)
    original_run = repair_verify.run_suite

    def failing(workspace, tests, suite, image, directory, *, _kernel):
        result = original_run(
            workspace, tests, suite, image, directory, _kernel=_kernel
        )
        if mode == "cancel":
            with Session(bridge_case[0]) as session:
                stage = session.get(StageRun, repair.comparison_id)
                stage.status = "cancelled"
                session.add(stage)
                session.commit()
        elif mode == "tool_failure":
            from semflow_research.domain.errors import AuditError

            raise AuditError("injected runtime/container failure")
        elif "int(" in (workspace / "app.py").read_text():
            result = parse_results(
                '<testsuite><testcase name="test_security"><failure message="AssertionError: still unsafe"/></testcase><testcase name="test_functional"/></testsuite>',
                1,
                suite,
            )
        return result

    monkeypatch.setattr(repair_verify, "run_suite", failing)
    result = run_stage(str(repair.comparison_id))
    if mode == "cancel":
        assert result.status == "cancelled"
    else:
        assert result.status == "completed", result.error
        assert result.result["status"] == (
            "failed" if mode == "assertion_failure" else "error"
        )
    with TestClient(app) as client:
        records = client.get(f"/api/v1/audits/{setup.audit_id}/repairs").json()
        assert records[0]["acceptance_ready"] is False
        response = client.post(
            f"/api/v1/repairs/{repair.record_id}/accept",
            json={
                "test_reviewed": True,
                "comparison_stage_id": str(repair.comparison_id),
                "reason": "Failed or cancelled validation cannot be accepted",
            },
        )
        assert response.status_code == 409
    with Session(bridge_case[0]) as session:
        assert session.get(StageRun, repair.stage_id).status == "completed"
        assert session.get(RepairRecord, repair.record_id).status == "checks_passed"
    before = len(suite_runner)
    run_stage(str(repair.comparison_id))
    assert len(suite_runner) == before


def test_comparison_projection_outage_recovers_without_tool_or_model_replay(
    bridge_case, scanner, suite_model, repair_model, syntax, suite_runner, monkeypatch
):
    setup = suite_ready(bridge_case, monkeypatch, suite_model)
    repair = repair_ready(bridge_case, monkeypatch, setup)
    commit, failed = Session.commit, []

    def outage(session):
        if not failed and any(
            isinstance(row, ResearchBinding)
            and row.stage_id == repair.comparison_id
            and row.manifest
            for row in (*session.new, *session.dirty)
        ):
            failed.append(True)
            raise RuntimeError("injected outage after comparison.json before DB commit")
        return commit(session)

    monkeypatch.setattr(Session, "commit", outage)
    assert run_stage(str(repair.comparison_id)).status == "failed"
    assert failed
    with Session(bridge_case[0]) as session:
        binding = session.exec(
            select(ResearchBinding).where(
                ResearchBinding.stage_id == repair.comparison_id
            )
        ).one()
        scientific = inspect(binding.execution_id, root=research_root())
        assert scientific.execution_status == "completed"
    monkeypatch.setattr(Session, "commit", commit)
    monkeypatch.setattr(
        repair_verify,
        "run_suite",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("tool replay")),
    )
    recovered = run_stage(str(repair.comparison_id))
    assert recovered.status == "completed" and recovered.result["status"] == "passed"
    with TestClient(app) as client:
        assert (
            client.get(f"/api/v1/audits/{setup.audit_id}/repairs").json()[0][
                "acceptance_ready"
            ]
            is True
        )


def test_project_tests_selection_remains_distinct_from_syntax(
    bridge_case, scanner, suite_model, repair_model, suite_runner, monkeypatch
):
    setup = suite_ready(bridge_case, monkeypatch, suite_model)
    observed = []

    def tests(workspace, language, profile, *, _kernel):
        assert language == "python" and profile == "python_pytest"
        ast.parse((workspace / "app.py").read_text())
        observed.append(profile)
        return {
            "status": "passed",
            "profile": profile,
            "output": "Explicit project-test tool substitute; source actually parsed",
        }

    monkeypatch.setattr("semflow_research.repair.repair.validate_workspace", tests)
    repaired = repair_ready(bridge_case, monkeypatch, setup, profile="python_pytest")
    with Session(bridge_case[0]) as session:
        record = session.get(RepairRecord, repaired.record_id)
        assert record.validation["isolated_tests"]["status"] == "passed"
        assert "syntax" not in record.validation
    assert observed == ["python_pytest"]


def test_followup_delivery_failure_preserves_repair_and_allows_explicit_comparison(
    bridge_case, scanner, suite_model, repair_model, syntax, suite_runner, monkeypatch
):
    setup = suite_ready(bridge_case, monkeypatch, suite_model)

    def unavailable(*args):
        raise RuntimeError("injected task publisher outage")

    monkeypatch.setattr("app.jobs.stages.execute_stage.delay", unavailable)
    # API creation can still be queued once; fail only publishing the follow-up.
    from app.application import stage_dispatch

    original = stage_dispatch.celery_publisher

    def publish(identifier, resume):
        with Session(bridge_case[0]) as session:
            stage = session.get(StageRun, UUID(identifier))
        if stage.kind == "repair":
            return
        return original(identifier, resume)

    monkeypatch.setattr(stage_dispatch, "celery_publisher", publish)
    repaired = repair_ready(bridge_case, monkeypatch, setup)
    assert repaired.followup_status == "failed"
    with Session(bridge_case[0]) as session:
        assert session.get(StageRun, repaired.stage_id).status == "completed"
        assert session.get(StageRun, repaired.comparison_id).status == "failed"
        assert session.get(RepairRecord, repaired.record_id).status == "checks_passed"
    calls = len(repair_model)
    run_stage(str(repaired.stage_id))
    assert len(repair_model) == calls
    monkeypatch.setattr("app.jobs.stages.execute_stage.delay", lambda *args: None)
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/repairs/{repaired.record_id}/verify",
            json={"suite_id": str(setup.suite_id)},
        )
        assert response.status_code == 201, response.text
        comparison_id = response.json()["id"]
    verified = run_stage(comparison_id)
    assert verified.status == "completed", verified.error
    assert verified.result["status"] == "passed"


@pytest.mark.parametrize("change", ["latest_decision", "manifest", "suite_files"])
def test_passed_comparison_cannot_accept_stale_confirmation_or_evidence(
    bridge_case,
    scanner,
    suite_model,
    repair_model,
    syntax,
    suite_runner,
    monkeypatch,
    change,
):
    setup = suite_ready(bridge_case, monkeypatch, suite_model)
    repair = repair_ready(bridge_case, monkeypatch, setup)
    assert run_stage(str(repair.comparison_id)).result["status"] == "passed"
    if change == "latest_decision":
        from app.persistence.stage_models import Candidate, Decision

        with Session(bridge_case[0]) as session:
            candidate = session.get(Candidate, UUID(setup.candidates[0]))
            session.add(
                Decision(
                    candidate_id=candidate.id,
                    actor_id=bridge_case[1],
                    status="excluded",
                    reason="Latest explicit operator decision revokes the prior confirmation",
                    evidence_ids=candidate.evidence_ids,
                )
            )
            session.commit()
    elif change == "suite_files":
        (
            ArtifactStore().directory(str(setup.suite_id)) / "tests/test_numeric.py"
        ).write_text("assert True\n")
    else:
        with Session(bridge_case[0]) as session:
            binding = session.exec(
                select(ResearchBinding).where(
                    ResearchBinding.stage_id == setup.suite_id
                )
            ).one()
            reference = binding.request["inputs"]["targets"]["candidates"]["artifact"]
            path = (
                research_root()
                / "artifacts"
                / reference["owner_execution_id"]
                / reference["path"]
            )
            path.write_text("altered immutable candidate bundle")
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/repairs/{repair.record_id}/accept",
            json={
                "test_reviewed": True,
                "comparison_stage_id": str(repair.comparison_id),
                "reason": "Stale evidence must never authorize patch acceptance",
            },
        )
        assert response.status_code == 409, response.text
    with Session(bridge_case[0]) as session:
        assert session.get(RepairRecord, repair.record_id).status == "checks_passed"
