"""Test doubles exercise ownership and acceptance gates; live Docker is checked separately."""

from uuid import UUID, uuid4

import pytest
from app.adapters.artifacts import ArtifactStore
from app.adapters.repair.patches import apply_changes
from app.api.routes import stages
from app.contracts.stages import ProposedChange
from app.core.db import engine
from app.persistence.stage_models import Candidate, RepairRecord, StageRun
from app.persistence.stage_repository import StageRepository
from app.services.evidence import EvidenceService
from app.services.repair_comparison import ComparisonService
from sqlmodel import Session, select


@pytest.fixture
def comparison_context(pipeline_context, monkeypatch):
    context = pipeline_context
    monkeypatch.setattr(stages.execute_stage, "delay", lambda *args: None)
    source = ArtifactStore().source(str(context["run_id"]))
    name = next(path.relative_to(source).as_posix() for path in source.rglob("*.py"))
    with Session(engine) as session:
        manual = StageRun(
            audit_id=context["run_id"], kind="manual_evidence", status="completed"
        )
        repair = StageRun(
            audit_id=context["run_id"],
            kind="repair",
            status="completed",
            inputs={"rescan": False},
        )
        session.add(manual)
        session.add(repair)
        session.commit()
        manual_id, repair_stage_id = manual.id, repair.id
    evidence = EvidenceService(str(context["run_id"]), str(manual_id), []).read(
        name, 1, 10
    )
    with Session(engine) as session:
        candidate = Candidate(
            audit_id=context["run_id"],
            stage_id=manual_id,
            origin="ai",
            status="confirmed",
            weakness="CWE-94",
            title="输入解释风险",
            description="输入进入动态解释，要求保持正常数字转换",
            location={"file": name, "line": 2},
            evidence_ids=[evidence["id"]],
        )
        session.add(candidate)
        session.commit()
        candidate_id = candidate.id
        record = RepairRecord(
            audit_id=context["run_id"],
            stage_id=repair_stage_id,
            status="checks_passed",
            candidate_ids=[str(candidate_id)],
            changes=[
                {
                    "file": name,
                    "old_text": "eval(value)",
                    "new_text": "int(value)",
                    "reason": "Restrict input to numeric conversion",
                }
            ],
            validation={
                "isolated_tests": {"status": "passed", "profile": "syntax"},
                "rescan": {"status": "not_run"},
            },
        )
        session.add(record)
        session.commit()
        repair_id = record.id
    directory = ArtifactStore().directory(str(repair_stage_id))
    diff = apply_changes(
        source,
        directory / "workspace",
        [
            ProposedChange(
                file=name,
                old_text="eval(value)",
                new_text="int(value)",
                reason="Restrict input to numeric conversion",
            )
        ],
        [name],
    )
    (directory / "repair.diff").write_text(diff, encoding="utf-8")
    suite = {
        "title": "数字转换的独立验收",
        "summary": "安全输入不会执行表达式，同时普通数字继续得到原来的转换结果。",
        "language": "python",
        "files": {
            "test_check.py": "def test_security():\n    assert True\ndef test_normal():\n    assert True\n"
        },
        "cases": [
            {
                "name": "test_security",
                "category": "security",
                "candidate_ids": [str(candidate_id)],
                "input_description": "带运算符的输入",
                "expected_behavior": "不得执行输入表达式",
            },
            {
                "name": "test_normal",
                "category": "functional",
                "candidate_ids": [],
                "input_description": "普通数字输入",
                "expected_behavior": "仍返回原有整数",
            },
        ],
        "assumptions": ["测试替身仅验证平台编排，不证明模型或真实项目质量"],
    }
    imported = context["client"].post(
        f"/api/v1/audits/{context['run_id']}/verification-suites/import",
        json={"suite": suite, "image": "test-only-image"},
    )
    assert imported.status_code == 201, imported.text
    suite_id = imported.json()["id"]
    from app.adapters.repair import verification_runner
    from app.services import repair_comparison

    monkeypatch.setattr(
        verification_runner, "resolve_image", lambda image: "sha256:test-double"
    )

    monkeypatch.setattr(
        repair_comparison, "resolve_image", lambda image: "sha256:test-double"
    )

    def fake_runner(workspace, _tests, _suite, _image, _output):
        return {
            "status": "completed",
            "cases": {
                "test_security": {
                    "status": "assertion_failed" if workspace == source else "passed"
                },
                "test_normal": {"status": "passed"},
            },
        }

    monkeypatch.setattr(repair_comparison, "run_suite", fake_runner)
    return {
        **context,
        "repair_id": str(repair_id),
        "suite_id": suite_id,
        "suite": suite,
        "directory": directory,
        "source": source,
        "name": name,
    }


@pytest.mark.parametrize(
    "pipeline_context",
    [
        {"app.py": "def calculate(value):\n    return eval(value)\n"},
        {"logic.py": "def convert(value):\n    return eval(value)\n"},
    ],
    indirect=True,
)
def test_multiple_projects_require_executed_comparison_and_human_review(
    comparison_context,
):
    context = comparison_context
    api, repair = context["client"], context["repair_id"]
    assert (
        api.post(
            f"/api/v1/repairs/{repair}/accept",
            json={"reason": "语法通过并不能确认漏洞修复有效"},
        ).status_code
        == 409
    )
    created = api.post(
        f"/api/v1/repairs/{repair}/verify", json={"suite_id": context["suite_id"]}
    )
    assert created.status_code == 201, created.text
    stage_id = created.json()["id"]
    assert StageRepository().claim(stage_id)
    ComparisonService(stage_id).run()
    rows = api.get(f"/api/v1/audits/{context['run_id']}/repairs").json()
    assert rows[0]["comparison"]["status"] == "passed"
    assert rows[0]["acceptance_ready"]
    assert rows[0]["validation"]["isolated_tests"]["profile"] == "syntax"
    assert (
        api.post(
            f"/api/v1/repairs/{repair}/accept",
            json={
                "reason": "尚未审阅测试断言不能接受补丁",
                "comparison_stage_id": stage_id,
            },
        ).status_code
        == 409
    )
    assert (
        api.post(
            f"/api/v1/repairs/{repair}/accept",
            json={
                "reason": "已审阅独立测试断言、前后结果和代码改动",
                "comparison_stage_id": stage_id,
                "test_reviewed": True,
            },
        ).status_code
        == 200
    )
    assert "eval(value)" in (context["source"] / context["name"]).read_text()
    with Session(engine) as session:
        acceptance = session.exec(
            select(StageRun).where(
                StageRun.audit_id == context["run_id"],
                StageRun.kind == "verification_acceptance",
            )
        ).one()
        assert acceptance.result["comparison_stage_id"] == stage_id


@pytest.mark.parametrize(
    "pipeline_context",
    [{"app.py": "def calculate(value):\n    return eval(value)\n"}],
    indirect=True,
)
def test_changed_patch_or_test_file_invalidates_comparison(comparison_context):
    context = comparison_context
    api = context["client"]
    stage_id = api.post(
        f"/api/v1/repairs/{context['repair_id']}/verify",
        json={"suite_id": context["suite_id"]},
    ).json()["id"]
    assert StageRepository().claim(stage_id)
    ComparisonService(stage_id).run()
    tests = ArtifactStore().directory(context["suite_id"]) / "tests" / "test_check.py"
    tests.write_text("# changed after verification", encoding="utf-8")
    rows = api.get(f"/api/v1/audits/{context['run_id']}/repairs").json()
    assert rows[0]["comparison"]["status"] == "stale"
    assert not rows[0]["acceptance_ready"]
    assert (
        api.post(
            f"/api/v1/repairs/{context['repair_id']}/accept",
            json={
                "reason": "不能接受测试内容已变化的补丁",
                "comparison_stage_id": stage_id,
                "test_reviewed": True,
            },
        ).status_code
        == 409
    )


@pytest.mark.parametrize(
    "pipeline_context",
    [{"app.py": "def calculate(value):\n    return eval(value)\n"}],
    indirect=True,
)
def test_suite_cannot_bind_foreign_candidate(comparison_context):
    context = comparison_context
    context["suite"]["cases"][0]["candidate_ids"] = [str(uuid4())]
    result = context["client"].post(
        f"/api/v1/audits/{context['run_id']}/verification-suites/import",
        json={"suite": context["suite"]},
    )
    assert result.status_code == 422


@pytest.mark.parametrize(
    "pipeline_context",
    [{"app.py": "def calculate(value):\n    return eval(value)\n"}],
    indirect=True,
)
def test_environment_preflight_does_not_enqueue_and_duplicate_click_reuses_job(
    comparison_context, monkeypatch
):
    from app.adapters.repair import verification_runner
    from app.domain.audit import AuditError

    context = comparison_context
    api = context["client"]
    url = f"/api/v1/repairs/{context['repair_id']}/verify"
    body = {"suite_id": context["suite_id"]}

    def unavailable(image):
        raise AuditError("验证服务未连接", code="environment_error")

    monkeypatch.setattr(verification_runner, "resolve_image", unavailable)
    assert api.post(url, json=body).status_code == 409
    with Session(engine) as session:
        assert not session.exec(
            select(StageRun).where(
                StageRun.audit_id == context["run_id"], StageRun.kind == "verification"
            )
        ).all()
    monkeypatch.setattr(
        verification_runner, "resolve_image", lambda image: "sha256:test-double"
    )
    first = api.post(url, json=body)
    second = api.post(url, json=body)
    assert first.status_code == second.status_code == 201
    assert first.json()["id"] == second.json()["id"]


@pytest.mark.parametrize(
    "pipeline_context",
    [{"app.py": "def calculate(value):\n    return eval(value)\n"}],
    indirect=True,
)
def test_imported_functional_case_cannot_reference_foreign_candidate(
    comparison_context,
):
    context = comparison_context
    context["suite"]["cases"][1]["candidate_ids"] = [str(uuid4())]
    result = context["client"].post(
        f"/api/v1/audits/{context['run_id']}/verification-suites/import",
        json={"suite": context["suite"]},
    )
    assert result.status_code == 422


@pytest.mark.parametrize(
    "pipeline_context",
    [{"app.py": "def calculate(value):\n    return eval(value)\n"}],
    indirect=True,
)
def test_failed_automatic_dispatch_preserves_completed_repair(
    comparison_context, monkeypatch
):
    context = comparison_context
    from app.services import repair_comparison

    def unavailable(*args):
        raise RuntimeError("queue unavailable")

    monkeypatch.setattr(repair_comparison, "_enqueue_after_repair", unavailable)
    failed = repair_comparison.enqueue_after_repair(
        context["repair_id"], context["suite_id"]
    )
    assert failed.kind == "verification" and failed.status == "failed"
    with Session(engine) as session:
        record = session.get(RepairRecord, UUID(context["repair_id"]))
        assert session.get(StageRun, record.stage_id).status == "completed"


@pytest.mark.parametrize(
    "pipeline_context",
    [{"app.py": "def calculate(value):\n    return eval(value)\n"}],
    indirect=True,
)
def test_selected_rescan_cannot_be_silently_omitted(comparison_context):
    from app.services.repair_comparison import acceptance_ready

    context = comparison_context
    with Session(engine) as session:
        record = session.get(RepairRecord, UUID(context["repair_id"]))
        stage = session.get(StageRun, record.stage_id)
        stage.inputs = {"rescan": True}
        session.add(stage)
        session.commit()
        assert not acceptance_ready(record, {"status": "passed"})


@pytest.mark.parametrize(
    "pipeline_context",
    [{"app.py": "def calculate(value):\n    return eval(value)\n"}],
    indirect=True,
)
def test_report_reader_guide_includes_actual_executed_comparison(comparison_context):
    context = comparison_context
    api = context["client"]
    created = api.post(
        f"/api/v1/repairs/{context['repair_id']}/verify",
        json={"suite_id": context["suite_id"]},
    )
    stage_id = created.json()["id"]
    assert StageRepository().claim(stage_id)
    ComparisonService(stage_id).run()
    report = api.get(f"/api/v1/audits/{context['run_id']}/report").json()
    checks = report["reader_guide"]["repairs"][0]["checks"]
    assert any(
        row["label"] == "漏洞验证" and row["status"] == "测试范围内通过"
        for row in checks
    )
