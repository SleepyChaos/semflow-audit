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


@pytest.mark.parametrize("outcome", ["missing", "skipped", "error"])
def test_candidate_uncertain_cases_cannot_stop_as_passed(
    selected, monkeypatch, outcome
):
    repair, _, _ = selected
    original = module.run_suite

    def run(workspace, tests, suite, image, output):
        data = original(workspace, tests, suite, image, output)
        if workspace != repair.service.evidence.root:
            if outcome == "missing":
                data["cases"].pop("test_security")
            else:
                data["cases"]["test_security"] = {"status": outcome}
        return data

    monkeypatch.setattr(module, "run_suite", run)
    result = module.check_selected_suite(repair, {"attempt": 2})
    assert result["status"] == "blocked"
    diagnosis = module.suite_diagnosis({"selected_suite": result})
    assert diagnosis["failed_cases"][0]["category"] == "security"
    assert diagnosis["candidate_identity"]["attempt"] == 2
    assert diagnosis["candidate_identity"]["stage_id"] == repair.service.stage_id


def test_feedback_retains_exact_candidate_and_functional_regression(selected):
    repair, _, _ = selected
    result = module.check_selected_suite(
        repair, {"attempt": 1, "proposal_hash": "candidate-one"}
    )
    diagnosis = module.suite_diagnosis({"selected_suite": result})
    assert result["status"] == "failed"
    assert diagnosis["candidate_identity"]["proposal_hash"] == "candidate-one"
    assert {r["category"] for r in diagnosis["failed_cases"]} == {
        "security",
        "functional",
    }
    assert all(
        r["input_description"] and r["expected_behavior"]
        for r in diagnosis["failed_cases"]
    )


def test_suite_without_both_categories_cannot_qualify_even_with_passes(selected):
    from app.services.verification_results import compare_runs

    runs = [
        {
            "before": {"status": "completed", "cases": {}},
            "after": {"status": "completed", "cases": {}},
        }
    ] * 2
    suite = SimpleNamespace(cases=[])
    assert not module._baseline_valid(suite, [r["before"] for r in runs])
    assert compare_runs(suite, runs)["status"] == "inconclusive"


@pytest.mark.parametrize(
    "expression, failed_category",
    [("eval(str(value))", "security"), ("int(value) + 1", "functional")],
)
def test_each_failed_category_drives_specific_feedback(
    selected, expression, failed_category
):
    repair, _, _ = selected
    folder = repair.directory / "attempt-3/workspace"
    folder.mkdir(parents=True)
    (folder / "app.py").write_text(f"def convert(value): return {expression}\n")
    result = module.check_selected_suite(
        repair, {"attempt": 3, "proposal_hash": "round-three"}
    )
    assert result["status"] == "failed"
    diagnosis = module.suite_diagnosis({"selected_suite": result})
    assert {row["category"] for row in diagnosis["failed_cases"]} == {failed_category}
    assert diagnosis["candidate_identity"]["attempt"] == 3
    assert diagnosis["candidate_identity"]["proposal_hash"] == "round-three"
