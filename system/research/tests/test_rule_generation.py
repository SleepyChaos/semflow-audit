"""RAG rule generation pauses on exact artifacts; continuation never regenerates."""

import json
from uuid import uuid4

import pytest
from rule_cases import install_substitutes, rule_spec
from semflow_contracts.actions import ControlCommand
from semflow_contracts.errors import ResearchError
from semflow_research.public.actions import approve
from semflow_research.public.rules import execute
from semflow_research.public.runs import inspect, resume
from semflow_research.public.runtime import prepare


def command_for(result, *, approved=True):
    return ControlCommand(
        command_id=uuid4(),
        execution_id=result.execution_id,
        action="resume",
        expected_revision=1,
        checkpoint_digest=result.pending_action.checkpoint.sha256,
        approval=approve(
            result.pending_action,
            actor={"kind": "human", "id": "explicit-test-operator"},
            approved=approved,
            reason="Operator reviewed these exact positive and negative fixtures",
        ),
        reason="Continue the original saved graph after explicit human review",
    )


@pytest.mark.parametrize("with_holdout", [False, True])
def test_rule_graph_freezes_rag_and_resumes_without_regeneration(
    research_case, settings, monkeypatch, with_holdout
):
    phases = []
    install_substitutes(monkeypatch, phases)
    case = research_case
    spec = rule_spec(case, settings)
    if with_holdout:
        from semflow_contracts.runs import validate_spec
        from semflow_research.public.holdouts import select

        value = spec.model_dump(mode="json")
        value["inputs"]["acceptance"]["holdout"] = select(
            "python-eval-review_anchor-v1"
        ).model_dump(mode="json")
        spec = validate_spec(value)
    result = execute(spec, prepare(spec, root=case.ledger.root, settings=settings))
    assert result.execution_status == "awaiting_input", result.failure
    assert phases == ["inspect_semantics", "generate_rule", "fixture_validation"]
    assert result.result.outcome == "draft"
    assert result.result.technical_validation is None
    assert len(result.result.development_checks) == 2
    assert inspect(spec.execution_id, root=case.ledger.root) == result
    command = command_for(result)
    final = resume(command, root=case.ledger.root, settings=settings)
    assert final.execution_status == "completed", final.failure
    assert final.result.outcome == ("checks_passed" if with_holdout else "draft")
    assert final.result.independent_validation.status == (
        "passed" if with_holdout else "not_evaluated"
    )
    assert phases == [
        "inspect_semantics",
        "generate_rule",
        "fixture_validation",
        "fixture_validation",
    ] + (["fixture_validation"] if with_holdout else [])
    assert final.result.rule == result.result.rule
    assert final.result.fixtures == result.result.fixtures
    assert final.result.technical_validation.status == "passed"
    assert final.usage.calls == result.usage.calls == 2
    assert resume(command, root=case.ledger.root, settings=settings) == final
    assert len(phases) == (5 if with_holdout else 4)
    manifest = json.loads(
        (
            case.ledger.root
            / "artifacts"
            / str(spec.execution_id)
            / final.manifest.path
        ).read_bytes()
    )
    assert manifest["revision"] == 2 and manifest[
        "previous_manifest"
    ] == result.manifest.model_dump(mode="json")


def test_rejected_fixtures_finish_without_technical_validation(
    research_case, settings, monkeypatch
):
    phases = []
    install_substitutes(monkeypatch, phases)
    spec = rule_spec(research_case, settings)
    result = execute(
        spec, prepare(spec, root=research_case.ledger.root, settings=settings)
    )
    assert result.execution_status == "awaiting_input", result.failure
    final = resume(
        command_for(result, approved=False),
        root=research_case.ledger.root,
        settings=settings,
    )
    assert final.execution_status == "completed", final.failure
    assert (
        final.result.outcome == "needs_revision"
        and final.result.technical_validation is None
    )
    assert phases.count("fixture_validation") == 1


@pytest.mark.parametrize(
    "changed", ["revision", "checkpoint", "subject", "query", "toolchain"]
)
def test_stale_rule_approval_does_not_consume_command_or_run_tools(
    research_case, settings, monkeypatch, changed
):
    phases = []
    install_substitutes(monkeypatch, phases)
    case = research_case
    spec = rule_spec(case, settings)
    context = prepare(spec, root=case.ledger.root, settings=settings)
    result = execute(spec, context)
    assert result.execution_status == "awaiting_input", result.failure
    command = command_for(result)
    if changed == "revision":
        command = command.model_copy(update={"expected_revision": 0})
    elif changed == "checkpoint":
        command = command.model_copy(update={"checkpoint_digest": "0" * 64})
    elif changed == "subject":
        command = command.model_copy(
            update={
                "approval": command.approval.model_copy(
                    update={"subject_digest": "0" * 64}
                )
            }
        )
    elif changed == "query":
        (context.workspace / "draft-0/candidate.json").write_text("{}")
    else:
        (settings.CODEQL_PACK_PATH / "codeql/python-all/test/qlpack.yml").write_text(
            "changed: true"
        )
    with pytest.raises(ResearchError):
        resume(command, root=case.ledger.root, settings=settings)
    assert phases == ["inspect_semantics", "generate_rule", "fixture_validation"]
    assert (
        inspect(spec.execution_id, root=case.ledger.root).execution_status
        == "awaiting_input"
    )
    with case.ledger._connect() as db:
        assert db.execute("SELECT count(*) FROM control_commands").fetchone()[0] == 0


def test_rule_approval_continues_in_a_fresh_python_process(
    research_case, settings, monkeypatch, tmp_path
):
    import os
    import subprocess
    import sys
    from pathlib import Path

    phases = []
    install_substitutes(monkeypatch, phases)
    spec = rule_spec(research_case, settings)
    waiting = execute(
        spec, prepare(spec, root=research_case.ledger.root, settings=settings)
    )
    assert waiting.execution_status == "awaiting_input", waiting.failure
    command = tmp_path / "resume.json"
    resources = tmp_path / "resources.json"
    command.write_text(command_for(waiting).model_dump_json())
    resources.write_text(settings.model_dump_json())
    system = Path(__file__).resolve().parents[2]
    script = """
import json, sys
from pathlib import Path
from pytest import MonkeyPatch
from rule_cases import install_substitutes
from semflow_contracts.actions import ControlCommand
from semflow_research.public.runtime import ToolSettings
from semflow_research.public.runs import resume
phases = []
with MonkeyPatch.context() as patch:
    install_substitutes(patch, phases)
    result = resume(ControlCommand.model_validate_json(Path(sys.argv[1]).read_bytes()),
        root=Path(sys.argv[2]), settings=ToolSettings.model_validate_json(Path(sys.argv[3]).read_bytes()))
assert phases == ['fixture_validation'], phases
assert result.execution_status == 'completed', result.failure
print(result.model_dump_json())
"""
    paths = [
        system / "contracts/src",
        system / "research/src",
        system / "research/tests",
    ]
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            script,
            str(command),
            str(research_case.ledger.root),
            str(resources),
        ],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": os.pathsep.join(map(str, paths))},
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    from semflow_contracts.results import ResultEnvelope

    final = ResultEnvelope.model_validate_json(completed.stdout)
    assert final.result.rule == waiting.result.rule
    assert final.result.fixtures == waiting.result.fixtures
    assert final.usage.calls == waiting.usage.calls == 2


def test_resumed_validation_tool_failure_keeps_immutable_diagnostics(
    research_case, settings, monkeypatch
):
    from semflow_research.domain.errors import AuditError
    from semflow_research.runtime.artifacts import LocalArtifacts
    from semflow_research.runtime.rule_diagnostics import read

    phases = []
    install_substitutes(monkeypatch, phases)
    spec = rule_spec(research_case, settings)
    root = research_case.ledger.root
    waiting = execute(spec, prepare(spec, root=root, settings=settings))
    assert waiting.execution_status == "awaiting_input"

    def unavailable(directory, *args, **kwargs):
        directory.mkdir(parents=True)
        (directory / "execution.log").write_text(
            "Explicit extraction failure; never successful empty output"
        )
        raise AuditError("Synthetic CodeQL extraction failure")

    monkeypatch.setattr("semflow_research.rules.rules.validate_fixtures", unavailable)
    final = resume(command_for(waiting), root=root, settings=settings)
    assert final.execution_status == "failed" and final.failure.code == "tool_failed"
    assert final.failure.detail is not None
    store = LocalArtifacts(root / "artifacts", spec.execution_id)
    diagnostic = read(store, final.failure.detail, spec.execution_id)
    assert "validation/execution.log" in diagnostic.files
    assert b"never successful empty" in store.read(
        diagnostic.files["validation/execution.log"]
    )
    __import__("shutil").rmtree(root / "workspaces" / str(spec.execution_id))
    assert inspect(spec.execution_id, root=root) == final
