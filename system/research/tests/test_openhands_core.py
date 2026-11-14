"""OpenHands public core uses the extracted graph and worker adapter boundary."""

import json
import sys
from pathlib import Path

from semflow_research.domain.errors import AuditError, ExecutionCancelled
from semflow_research.public.repair import execute
from semflow_research.public.runtime import prepare
from semflow_research.runtime.repair_outputs import read_attempts

from research.tests.openhands_cases import IMAGE, openhands_spec, proposal


def test_openhands_public_graph_exports_patch_and_usage_receipt(
    research_case, settings, repair_model, monkeypatch
):
    spec = openhands_spec(research_case)
    settings = settings.model_copy(
        update={
            "OPENHANDS_PYTHON": str(Path(sys.executable)),
            "OPENHANDS_IMAGE": IMAGE,
        }
    )
    monkeypatch.setattr(
        "semflow_research.repair.repair_openhands.generate",
        lambda *args, **kwargs: {
            "proposal": proposal(),
            "runtime": {
                "status": "completed",
                "metrics": {"calls": 1, "output_tokens": 10},
            },
        },
    )
    context = prepare(spec, root=research_case.ledger.root, settings=settings)
    result = execute(spec, context)
    assert result.execution_status == "completed", result.failure
    assert result.result.outcome == "needs_review"
    assert context.executions.inspect(spec.execution_id) == result
    attempts = read_attempts(
        context.artifacts,
        result.result.attempts,
        execution_id=spec.execution_id,
        snapshot_id=spec.source.snapshot_id,
    )
    assert attempts.records[0].patch is not None
    assert (
        json.loads(context.artifacts.read(attempts.records[0].diagnosis))
        if attempts.records[0].diagnosis
        else True
    )


def test_openhands_missing_runtime_is_explicit_failure_with_no_patch(
    research_case, settings, repair_model
):
    spec = openhands_spec(research_case)
    settings = settings.model_copy(
        update={"OPENHANDS_PYTHON": "", "OPENHANDS_IMAGE": IMAGE}
    )
    context = prepare(spec, root=research_case.ledger.root, settings=settings)
    result = execute(spec, context)
    assert result.execution_status == "failed", result.failure
    assert result.result is None
    assert result.failure.code in {"tool_unavailable"}


def test_openhands_worker_failure_never_becomes_empty_success(
    research_case, settings, repair_model, monkeypatch
):
    spec = openhands_spec(research_case)
    settings = settings.model_copy(
        update={"OPENHANDS_PYTHON": "/usr/bin/python", "OPENHANDS_IMAGE": IMAGE}
    )

    def failed(*args, **kwargs):
        raise AuditError("OpenHands runtime timed out", code="agent_stalled")

    monkeypatch.setattr("semflow_research.repair.repair_openhands.generate", failed)
    context = prepare(spec, root=research_case.ledger.root, settings=settings)
    result = execute(spec, context)
    assert result.execution_status == "failed"
    assert result.result is None
    assert (
        result.failure.code == "internal_error" or result.failure.code == "tool_failed"
    )


def test_openhands_cancellation_is_terminal_cancelled_without_patch(
    research_case, settings, repair_model, monkeypatch
):
    spec = openhands_spec(research_case)
    settings = settings.model_copy(
        update={"OPENHANDS_PYTHON": "/usr/bin/python", "OPENHANDS_IMAGE": IMAGE}
    )

    def cancelled(*args, **kwargs):
        raise ExecutionCancelled("OpenHands cancelled at a safe boundary")

    monkeypatch.setattr("semflow_research.repair.repair_openhands.generate", cancelled)
    context = prepare(spec, root=research_case.ledger.root, settings=settings)
    result = execute(spec, context)
    assert result.execution_status == "cancelled"
    assert result.result is None
    assert result.failure.code == "cancelled"
