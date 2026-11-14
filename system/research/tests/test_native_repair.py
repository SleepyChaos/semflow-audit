"""Native graph executes directly with frozen human decisions and source scope."""

import json
import os

import pytest
from semflow_contracts.runs import validate_spec
from semflow_research.public.repair import execute
from semflow_research.public.runtime import prepare
from semflow_research.runtime.repair_outputs import read_attempts

from research.tests.native_cases import repair_spec


@pytest.mark.parametrize(
    "executor",
    [
        "fixture",
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
def test_native_graph_exports_patch_attempt_and_actual_source_receipts(
    research_case, settings, repair_model, syntax, executor, monkeypatch
):
    case = research_case
    spec = repair_spec(case)
    if executor == "docker":
        from semflow_research.adapters.repair.validator import validate_workspace

        settings = settings.model_copy(
            update={
                "VALIDATOR_PYTHON_IMAGE": os.environ["SEMFLOW_RESEARCH_VALIDATOR_IMAGE"]
            }
        )

        def real_syntax(workspace, language, profile, *, _kernel):
            syntax.append((workspace / "app.py").read_text())
            return validate_workspace(workspace, language, profile, _kernel=_kernel)

        monkeypatch.setattr(
            "semflow_research.repair.repair.validate_workspace", real_syntax
        )
    context = prepare(spec, root=case.ledger.root, settings=settings)
    result = execute(spec, context)
    assert result.execution_status == "completed", result.failure
    assert result.result.outcome == "checks_passed"
    assert {check.kind for check in result.result.checks} == {
        "syntax",
        "semantic_consistency",
    }
    assert result.usage.calls == 3 and repair_model == [
        "inspect_semantics",
        "propose_patch",
        "assess_patch_contract",
    ]
    assert syntax == ["value = int(input())\n"]
    assert b"-value = eval(input())" in context.artifacts.read(result.result.patch)
    history = read_attempts(
        context.artifacts,
        result.result.attempts,
        execution_id=spec.execution_id,
        snapshot_id=case.snapshot.snapshot_id,
    )
    assert len(history.records) == 1 and history.records[0].selected
    assert history.records[0].context_digest == history.records[0].context.sha256
    assert result.result.patched_source.tree_sha256 != spec.source.tree_sha256
    assert result.result.patched_source.archive.kind == "patched_source"
    assert (
        context.source_root.joinpath("app.py").read_text() == "value = eval(input())\n"
    )
    assert execute(spec, context) == result and len(repair_model) == 3
    assert context.executions.inspect(spec.execution_id) == result
    if executor == "docker" and os.environ.get("SEMFLOW_RESEARCH_GATE_REPORT"):
        import shutil
        from pathlib import Path

        directory = Path(os.environ["SEMFLOW_RESEARCH_GATE_REPORT"]) / str(
            spec.execution_id
        )
        directory.mkdir(parents=True, exist_ok=False)
        (directory / "result.json").write_text(result.model_dump_json(indent=2))
        (directory / "scope.json").write_text(
            json.dumps(
                {
                    "scope": "one synthetic native repair; real Docker syntax validation",
                    "model": "scripted fixture",
                    "operator": "scripted test actor",
                    "image": settings.VALIDATOR_PYTHON_IMAGE,
                    "method_fingerprint": "fixture placeholder; not a production algorithm equivalence claim",
                },
                indent=2,
            )
            + "\n"
        )
        shutil.copytree(case.ledger.root, directory / "research")


def test_model_support_without_operator_decision_cannot_authorize_repair(
    research_case, settings, repair_model, syntax
):
    spec = repair_spec(research_case, confirmed=False)
    context = prepare(spec, root=research_case.ledger.root, settings=settings)
    result = execute(spec, context)
    assert (
        result.execution_status == "failed"
        and result.failure.code == "invalid_contract"
    )
    assert result.result is None and repair_model == syntax == []


def test_disabled_consistency_check_is_not_executed_or_reported_passed(
    research_case, settings, repair_model, syntax
):
    spec = repair_spec(research_case, consistency=False)
    context = prepare(spec, root=research_case.ledger.root, settings=settings)
    result = execute(spec, context)
    assert result.execution_status == "completed", result.failure
    assert repair_model == ["inspect_semantics", "propose_patch"]
    assert [check.kind for check in result.result.checks] == ["syntax"]


def test_no_selected_checks_leaves_patch_unverified(
    research_case, settings, repair_model, syntax
):
    value = repair_spec(research_case, consistency=False).model_dump(mode="json")
    value["inputs"]["validation_plan"]["syntax"] = False
    spec = validate_spec(value)
    context = prepare(spec, root=research_case.ledger.root, settings=settings)
    result = execute(spec, context)
    assert result.execution_status == "completed", result.failure
    assert result.result.patch is not None and result.result.outcome == "needs_review"
    assert result.result.checks == () and syntax == []
    assert repair_model == ["inspect_semantics", "propose_patch"]


def test_validation_environment_failure_is_not_a_passing_patch(
    research_case, settings, repair_model, monkeypatch
):
    from semflow_research.domain.errors import AuditError

    def unavailable(*args, **kwargs):
        raise AuditError("Scripted validation image is unavailable")

    monkeypatch.setattr(
        "semflow_research.repair.repair.validate_workspace", unavailable
    )
    spec = repair_spec(research_case)
    context = prepare(spec, root=research_case.ledger.root, settings=settings)
    result = execute(spec, context)
    assert result.execution_status == "completed", result.failure
    assert result.result.outcome == "needs_review"
    assert result.result.checks[0].status == "error"
    assert repair_model == ["inspect_semantics", "propose_patch"]
    attempts = read_attempts(
        context.artifacts,
        result.result.attempts,
        execution_id=spec.execution_id,
        snapshot_id=spec.source.snapshot_id,
    )
    assert attempts.records[0].diagnosis is not None
    assert (
        json.loads(context.artifacts.read(attempts.records[0].diagnosis))["category"]
        == "environment"
    )


def test_changed_attempt_artifact_is_rejected_on_inspection(
    research_case, settings, repair_model, syntax
):
    from semflow_contracts.errors import ResearchError

    spec = repair_spec(research_case)
    context = prepare(spec, root=research_case.ledger.root, settings=settings)
    result = execute(spec, context)
    attempts = read_attempts(
        context.artifacts,
        result.result.attempts,
        execution_id=spec.execution_id,
        snapshot_id=spec.source.snapshot_id,
    )
    proposal = attempts.records[0].proposal
    (context.artifacts.root / str(spec.execution_id) / proposal.path).write_bytes(
        b"changed proposal"
    )
    with pytest.raises(ResearchError, match="Artifact bytes"):
        context.executions.inspect(spec.execution_id)


def test_completed_repair_inspection_uses_refs_after_working_copy_is_removed(
    research_case, settings, repair_model, syntax
):
    import shutil

    spec = repair_spec(research_case)
    context = prepare(spec, root=research_case.ledger.root, settings=settings)
    result = execute(spec, context)
    shutil.rmtree(context.workspace)
    assert context.executions.inspect(spec.execution_id) == result


def test_prompt_revision_is_not_relabelled_as_algorithm_revision(
    research_case, settings, repair_model, syntax
):
    from semflow_research.state.models import ExecutionRecord

    value = repair_spec(research_case).model_dump(mode="json")
    value["prompts"][0]["version"] = "prompt-variant-b"
    spec = validate_spec(value)
    context = prepare(spec, root=research_case.ledger.root, settings=settings)
    result = execute(spec, context)
    assert result.execution_status == "completed", result.failure
    calls = context.records.get(ExecutionRecord, spec.execution_id).model_calls
    assert {row["method_version"] for row in calls} == {"4"}
    assert {row["prompt_version"] for row in calls} == {"prompt-variant-b"}
