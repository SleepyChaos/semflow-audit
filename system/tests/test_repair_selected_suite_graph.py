"""The production repair graph corrects syntax-valid code using selected assertions."""

import os
from runpy import run_path

import pytest
from app.persistence.stage_repository import StageRepository
from app.services.repair import RepairService
from app.workflows.repair import build_repair_graph

from tests.test_semantic_development import InspectModel, ready
from tests.test_verification_lifecycle import comparison_context  # noqa: F401

# Reused fixtures are intentionally injected by pytest.
# ruff: noqa: F811


@pytest.mark.parametrize("first_candidate", ["str(value)", "missing_conversion(value)"])
@pytest.mark.parametrize(
    "executor",
    [
        "trusted_fixture",
        pytest.param(
            "docker",
            marks=[
                pytest.mark.integration,
                pytest.mark.skipif(
                    os.environ.get("AUDIT_RUN_REAL_TOOLS") != "1",
                    reason="explicit real Docker opt-in",
                ),
            ],
        ),
    ],
)
@pytest.mark.parametrize(
    "pipeline_context",
    [{"app.py": "def calculate(value):\n    return eval(value)\n"}],
    indirect=True,
)
def test_selected_executed_assertions_drive_real_graph_retry(
    comparison_context, monkeypatch, executor, first_candidate
):
    import ast
    import json

    from app.services import repair as repair_module
    from app.services import repair_comparison, repair_suite_checks

    context = comparison_context
    from app.core.audit_config import audit_settings

    image_spec = (
        audit_settings.VALIDATOR_PYTHON_IMAGE
        if executor == "docker"
        else "test-only-image"
    )
    suite = context["suite"]
    suite["files"] = {
        "test_check.py": "import pytest\nfrom app import calculate\ndef test_security():\n    with pytest.raises(ValueError): calculate('2+2')\ndef test_normal():\n    assert calculate('42') == 42\n"
    }
    imported = context["client"].post(
        f"/api/v1/audits/{context['run_id']}/verification-suites/import",
        json={"suite": suite, "image": image_spec},
    )
    assert imported.status_code == 201
    suite_id = imported.json()["id"]
    queued = []
    monkeypatch.setattr(
        repair_comparison, "enqueue_after_repair", lambda *args: queued.append(args)
    )
    if executor != "docker":
        monkeypatch.setattr(
            "app.adapters.repair.verification_runner.resolve_image",
            lambda image: "sha256:test-only",
        )
        monkeypatch.setattr(repair_suite_checks, "resolve_image", lambda image: image)
    real_runner = repair_suite_checks.run_suite
    executed = []

    def run(workspace, _tests, _suite, image, output):
        executed.append((str(workspace), image))
        if executor == "docker":
            return real_runner(workspace, _tests, _suite, image, output)
        output.mkdir(parents=True)
        calculate = run_path(str(workspace / "app.py"))["calculate"]
        cases = {}
        for name, value in [("test_security", "2+2"), ("test_normal", "42")]:
            try:
                result = calculate(value)
                passed = name == "test_normal" and result == 42
                cases[name] = {"status": "passed" if passed else "assertion_failed"}
            except ValueError:
                cases[name] = {
                    "status": "passed" if name == "test_security" else "error"
                }
            except NameError as error:
                cases[name] = {
                    "status": "error",
                    "exception_type": "NameError",
                    "exception_message": str(error),
                    "exception_file": "app.py",
                    "exception_line": 2,
                }
        return {"status": "completed", "cases": cases}

    monkeypatch.setattr(repair_suite_checks, "run_suite", run)

    def syntax(workspace, *_):
        ast.parse(workspace.joinpath("app.py").read_text())
        return {"status": "passed", "output": "actual syntax parsed"}

    monkeypatch.setattr(repair_module, "validate_workspace", syntax)
    proposals = []
    assessments = []

    def respond(payload):
        if payload["phase"] == "inspect_semantics":
            return ready(payload)
        if payload["phase"] == "assess_patch_contract":
            assessments.append(payload)
            return {
                "constraints": [
                    {
                        "fact_index": i,
                        "status": "consistent",
                        "explanation": "Scripted reviewer misses a runtime conversion regression",
                        "evidence_ids": [payload["evidence"][0]["id"]],
                    }
                    for i in payload["required_fact_indices"]
                ],
                "callers": [],
                "limitation": "Scripted assessment explicitly cannot replace executed tests",
            }
        assert payload["phase"] == "propose_patch"
        proposals.append(payload)
        return {
            "changes": [
                {
                    "file": "app.py",
                    "old_text": "eval(value)",
                    "new_text": first_candidate
                    if len(proposals) == 1
                    else "int(value)",
                    "reason": "Preserve numeric conversion without dynamic interpretation",
                }
            ],
            "summary": "Use explicit conversion while preserving the selected normal behavior",
        }

    response = context["client"].post(
        f"/api/v1/audits/{context['run_id']}/repair",
        json={
            "candidate_ids": suite["cases"][0]["candidate_ids"],
            "allowed_paths": ["app.py"],
            "verification_suite_id": suite_id,
            "rescan": False,
        },
    )
    assert response.status_code == 201
    stage_id = response.json()["id"]
    assert response.json()["prompt_version"] == "3"
    assert StageRepository().claim(stage_id)
    service = RepairService(stage_id, InspectModel(respond))
    result = build_repair_graph(service).invoke({})
    assert result["passed"] and result["attempt"] == 2
    assert len(executed) == 6
    assert len({image for _, image in executed}) == 1
    assert all(image.startswith("sha256:") for _, image in executed)
    assert (
        sum(workspace == str(service.evidence.root) for workspace, _ in executed) == 2
    )
    first = json.loads((service.directory / "attempt-1/checks.json").read_text())
    assert first["isolated_tests"]["status"] == "passed"
    assert "semantic_contract" not in first
    assert len(assessments) == 1  # Failed candidate never consumes model review.
    assert result["checks"]["semantic_contract"]["status"] == "passed"
    assert first["selected_suite"]["status"] == "failed"
    assert proposals[1]["failure_feedback"]["category"] == "implementation"
    if first_candidate.startswith("missing"):
        assert (
            proposals[1]["failure_feedback"]["runtime_errors"][0]["exception_type"]
            == "NameError"
        )
        assert (
            proposals[1]["failure_feedback"]["runtime_errors"][0]["candidate_file"]
            == "app.py"
        )
    assert proposals[1]["checks"]["selected_suite"]["cases"]
    assert "with pytest.raises" not in str(proposals[1])
    assert queued == [(result["repair_id"], service.inputs.verification_suite_id)]
    assert (
        service.evidence.root.joinpath("app.py").read_text()
        == "def calculate(value):\n    return eval(value)\n"
    )
