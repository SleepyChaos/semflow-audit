"""Separate rule validation reuses the native checks on exact approved subjects."""

import shutil
from uuid import uuid4

import pytest
from semflow_contracts.errors import ResearchError
from semflow_contracts.evidence import ActorRef
from semflow_contracts.runs import validate_spec
from semflow_research.public.actions import decision_command
from semflow_research.public.rule_validation import assemble
from semflow_research.public.runs import execute, inspect

from research.tests.rule_cases import install_substitutes, rule_spec


def pending(case, settings, monkeypatch, *, holdout):
    phases = []
    install_substitutes(monkeypatch, phases)
    spec = rule_spec(case, settings)
    if holdout:
        from semflow_research.public.holdouts import select

        value = spec.model_dump(mode="json")
        value["inputs"]["acceptance"]["holdout"] = select(
            "python-eval-review_anchor-v1"
        ).model_dump(mode="json")
        spec = validate_spec(value)
    waiting = execute(spec, root=case.ledger.root, settings=settings)
    assert waiting.execution_status == "awaiting_input", waiting.failure
    command = decision_command(
        waiting.execution_id,
        root=case.ledger.root,
        actor=ActorRef(kind="human", id="test-operator"),
        approved=True,
        reason="Reviewed these exact positive and negative fixtures",
    )
    return waiting, command, phases


@pytest.mark.parametrize("holdout", [False, True])
def test_separate_validation_preserves_original_refs_and_needs_no_generation_workspace(
    research_case, settings, monkeypatch, holdout
):
    case = research_case
    waiting, command, phases = pending(case, settings, monkeypatch, holdout=holdout)
    spec = assemble(command, root=case.ledger.root)
    shutil.rmtree(case.ledger.root / "workspaces" / str(waiting.execution_id))
    phases.clear()
    final = execute(spec, root=case.ledger.root, settings=settings)
    assert final.execution_status == "completed", final.failure
    assert final.result.rule == waiting.result.rule
    assert final.result.fixtures == waiting.result.fixtures
    assert final.result.technical_validation.status == "passed"
    assert final.result.independent_validation.status == (
        "passed" if holdout else "not_evaluated"
    )
    assert final.result.outcome == ("checks_passed" if holdout else "draft")
    assert phases == ["fixture_validation"] * (2 if holdout else 1)
    assert final.usage.calls == 0
    assert inspect(waiting.execution_id, root=case.ledger.root) == waiting
    assert inspect(final.execution_id, root=case.ledger.root) == final
    assert execute(spec, root=case.ledger.root, settings=settings) == final
    assert len(phases) == (2 if holdout else 1)


@pytest.mark.parametrize(
    "changed", ["approval", "holdout", "query", "fixtures", "replay", "source"]
)
def test_separate_validation_rejects_semantic_changes_before_tools(
    research_case, settings, monkeypatch, changed
):
    case = research_case
    waiting, command, phases = pending(case, settings, monkeypatch, holdout=True)
    spec = assemble(command, root=case.ledger.root)
    value = spec.model_dump(mode="json")
    if changed == "approval":
        value["inputs"]["approval"]["subject_digest"] = "0" * 64
    elif changed == "holdout":
        value["inputs"]["holdout"] = None
    elif changed == "query":
        value["inputs"]["query"]["version"] = "another-method"
    elif changed == "fixtures":
        value["inputs"]["fixtures"] = waiting.result.coverage_analysis.model_dump(
            mode="json"
        )
    elif changed == "replay":
        value["inputs"]["project_replay"] = waiting.result.coverage_analysis.model_dump(
            mode="json"
        )
    else:
        value["source"]["snapshot_id"] = str(uuid4())
    phases.clear()
    final = execute(validate_spec(value), root=case.ledger.root, settings=settings)
    assert final.execution_status == "failed"
    assert final.failure.code in {"approval_stale", "identity_mismatch"}
    assert phases == []
    assert inspect(waiting.execution_id, root=case.ledger.root) == waiting


def test_separate_validation_preserves_failed_positive_negative_checks(
    research_case, settings, monkeypatch
):
    case = research_case
    _, command, _ = pending(case, settings, monkeypatch, holdout=True)
    spec = assemble(command, root=case.ledger.root)
    from semflow_research.rules import rules

    original = rules.validate_fixtures

    def fail(*args, **kwargs):
        result = original(*args, **kwargs)
        result["tests"]["negative"]["status"] = "failed"
        result["tests"]["negative"]["actual"] = [("negative.py", 1)]
        return {**result, "status": "failed"}

    monkeypatch.setattr(rules, "validate_fixtures", fail)
    final = execute(spec, root=case.ledger.root, settings=settings)
    assert final.execution_status == "completed", final.failure
    assert final.result.technical_validation.status == "failed"
    assert final.result.outcome == "draft"


def test_separate_validation_refuses_rejected_decision(
    research_case, settings, monkeypatch
):
    _, command, _ = pending(research_case, settings, monkeypatch, holdout=False)
    command = command.model_copy(
        update={"approval": command.approval.model_copy(update={"approved": False})}
    )
    with pytest.raises(ResearchError, match="explicit approved"):
        assemble(command, root=research_case.ledger.root)
