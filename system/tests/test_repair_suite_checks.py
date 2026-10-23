"""Executed selected assertions drive feedback; unchanged baselines execute once."""

from runpy import run_path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from app.adapters.snapshot import snapshot_digest
from app.contracts.verification import VerificationCase
from app.domain.audit import AuditError
from app.services import repair_suite_checks as module


@pytest.fixture
def selected(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    source.joinpath("app.py").write_text("def convert(value): return eval(value)\n")
    directory = tmp_path / "stage"
    for number, expression in [(1, "str(value)"), (2, "int(value)")]:
        path = directory / f"attempt-{number}" / "workspace"
        path.mkdir(parents=True)
        path.joinpath("app.py").write_text(f"def convert(value): return {expression}\n")
    suite = SimpleNamespace(
        cases=[
            VerificationCase(
                name="test_security",
                category="security",
                candidate_ids=[uuid4()],
                input_description="表达式输入",
                expected_behavior="不得解释计算",
            ),
            VerificationCase(
                name="test_normal",
                category="functional",
                input_description="正常数字输入",
                expected_behavior="保持整数返回",
            ),
        ]
    )
    stage = SimpleNamespace(
        id=uuid4(),
        result={"suite_hash": "frozen-suite", "test_files_hash": "frozen-tests"},
    )
    monkeypatch.setattr(
        module, "read_suite", lambda *args: (stage, suite, tmp_path / "tests")
    )
    monkeypatch.setattr(module, "resolve_image", lambda value: value)
    executed = []

    def run(workspace, tests, suite, image, output):
        output.mkdir(parents=True)
        executed.append(str(workspace))
        # This runner executes only the trusted synthetic module authored in
        # this fixture. Production keeps the constrained Docker run_suite.
        namespace = run_path(str(workspace / "app.py"))
        convert = namespace["convert"]
        try:
            convert("2+2")
            security = False
        except ValueError:
            security = True
        normal = convert("42") == 42
        return {
            "status": "completed",
            "cases": {
                "test_security": {
                    "status": "passed" if security else "assertion_failed"
                },
                "test_normal": {"status": "passed" if normal else "assertion_failed"},
            },
        }

    monkeypatch.setattr(module, "run_suite", run)
    service = SimpleNamespace(
        inputs=SimpleNamespace(verification_suite_id=stage.id),
        stage=SimpleNamespace(audit_id=uuid4()),
        stage_id=str(uuid4()),
        repository=SimpleNamespace(active=lambda *args: None),
        evidence=SimpleNamespace(
            root=source, audit=SimpleNamespace(snapshot_hash=snapshot_digest(source))
        ),
    )
    repair = SimpleNamespace(
        service=service,
        directory=directory,
        context=lambda state: {"verification_image_id": "sha256:pinned"},
    )
    return repair, executed, source


def test_real_selected_assertions_fail_then_pass_and_reuse_baseline(selected):
    repair, calls, source = selected
    first = module.check_selected_suite(repair, {"attempt": 1})
    assert first["status"] == "failed"
    assert (
        module.suite_diagnosis({"selected_suite": first})["category"]
        == "implementation"
    )
    second = module.check_selected_suite(repair, {"attempt": 2})
    assert second["status"] == "passed"
    assert calls.count(str(source)) == 2
    assert len(calls) == 6  # Two original runs + two per actual candidate.
    assert module.check_selected_suite(repair, {"attempt": 2}) == second
    assert len(calls) == 6
    assert (
        source.joinpath("app.py").read_text()
        == "def convert(value): return eval(value)\n"
    )


def test_nonreproducing_baseline_stops_before_candidate_and_not_implementation(
    selected,
):
    repair, calls, source = selected
    source.joinpath("app.py").write_text("def convert(value): return int(value)\n")
    repair.service.evidence.audit.snapshot_hash = snapshot_digest(source)
    result = module.check_selected_suite(repair, {"attempt": 1})
    assert result["status"] == "blocked"
    assert (
        module.suite_diagnosis({"selected_suite": result})["category"] == "inconclusive"
    )
    assert calls == [str(source), str(source)]


def test_changed_execution_receipt_is_rejected(selected):
    repair, _, _ = selected
    module.check_selected_suite(repair, {"attempt": 1})
    path = repair.directory / "selected-suite-baseline/run-1/execution.json"
    path.write_text(path.read_text().replace("assertion_failed", "passed"))
    with pytest.raises(AuditError, match="收据"):
        module.check_selected_suite(repair, {"attempt": 2})


def test_uncalibrated_path_does_not_hide_proven_failures_or_become_a_pass(
    selected,
    monkeypatch,
):
    repair, calls, source = selected
    _, suite, _ = module.read_suite(None, None)
    suite.cases.append(
        VerificationCase(
            name="test_original_xml",
            category="functional",
            input_description="原程序的 XML 功能",
            expected_behavior="应解析 XML",
        )
    )
    original_runner = module.run_suite

    def runner(*args):
        result = original_runner(*args)
        result["cases"]["test_original_xml"] = {
            "status": "error",
            "exception_type": "TypeError",
        }
        return result

    monkeypatch.setattr(module, "run_suite", runner)
    first = module.check_selected_suite(repair, {"attempt": 1})
    assert first["status"] == "failed" and first["category"] == "implementation"
    assert first["unresolved_baseline_cases"] == ["test_original_xml"]
    diagnosis = module.suite_diagnosis({"selected_suite": first})
    assert all(
        "test_original_xml" not in row for row in diagnosis["violated_constraints"]
    )
    second = module.check_selected_suite(repair, {"attempt": 2})
    assert second["status"] == "blocked" and second["category"] == "inconclusive"
    assert calls.count(str(source)) == 2
