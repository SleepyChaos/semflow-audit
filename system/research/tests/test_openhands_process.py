"""Exercise real subprocess/handshake/artifact boundaries with a scripted worker.

The SDK/model and Docker transport are explicit substitutes. The parent adapter,
process lifecycle, durable budgets, graph, application and receipts are real.
"""

import json
import shutil

import pytest
from semflow_contracts.runs import validate_spec
from semflow_research.adapters.repair.openhands_receipts import read
from semflow_research.public.repair import execute
from semflow_research.public.runtime import prepare
from semflow_research.runtime.calls import CallJournal
from semflow_research.runtime.repair_outputs import read_attempts

from research.tests.openhands_cases import openhands_spec
from research.tests.openhands_process_cases import resources


def test_changed_worker_bytes_rejected_before_external_execution(
    research_case, settings, repair_model, monkeypatch, tmp_path
):
    spec = openhands_spec(research_case)
    configured = resources(tmp_path, settings, monkeypatch)
    context = prepare(spec, root=research_case.ledger.root, settings=configured)
    runner = configured.OPENHANDS_RUNNER
    runner.write_text(runner.read_text() + "\n# changed after the resource snapshot\n")
    result = execute(spec, context)
    assert (
        result.execution_status == "failed" and result.failure.code == "integrity_error"
    )
    assert not (tmp_path / "docker.log").exists()
    assert result.failure.detail.schema_version == "semflow.openhands-receipt/1"
    assert context.executions.inspect(spec.execution_id) == result


@pytest.mark.parametrize(
    "mode", ["success", "failed", "timeout", "second_call", "method_cap", "cancel"]
)
def test_openhands_real_process_receipts_and_budget(
    research_case, settings, repair_model, monkeypatch, tmp_path, mode
):
    spec = openhands_spec(research_case)
    value = spec.model_dump(mode="json")
    value["inputs"]["openhands"]["timeout_seconds"] = 1 if mode == "timeout" else 10
    if mode == "second_call":
        value["policy"]["max_calls"] = 2  # Initial semantic call + one SDK call.
    if mode == "method_cap":
        value["inputs"]["method_policy"]["model_call_limit"] = 2
    spec = validate_spec(value)
    context = prepare(
        spec,
        root=research_case.ledger.root,
        settings=resources(tmp_path, settings, monkeypatch, mode=mode),
    )
    if mode == "cancel":
        from semflow_research.domain.errors import ExecutionCancelled

        original = context.control.check_active

        def cancel(execution_id):
            if (context.workspace / "openhands/calls").exists():
                raise ExecutionCancelled("Explicit cancellation at worker boundary")
            return original(execution_id)

        monkeypatch.setattr(context.control, "check_active", cancel)
    result = execute(spec, context)
    assert result.execution_status == (
        "completed"
        if mode in {"success", "method_cap"}
        else "cancelled"
        if mode == "cancel"
        else "failed"
    ), result.failure
    if mode in {"success", "method_cap"}:
        attempts = read_attempts(
            context.artifacts,
            result.result.attempts,
            execution_id=spec.execution_id,
            snapshot_id=spec.source.snapshot_id,
        )
        reference = attempts.records[0].engine_receipt
        assert result.result.patch is not None
        if mode == "method_cap":
            assert result.result.outcome == "needs_review"
            assert result.usage.calls == 2 and repair_model == ["inspect_semantics"]
        assert any(
            row.provider == "openhands/openai-compatible"
            and row.calls == 1
            and row.input_tokens == 30
            for row in result.usage.by_provider
        )
    else:
        reference = result.failure.detail
        assert result.result is None
        assert result.failure.code == (
            "cancelled"
            if mode == "cancel"
            else "budget_exhausted"
            if mode in {"second_call", "method_cap"}
            else "tool_failed"
        )
    body = read(context.artifacts, reference, execution_id=spec.execution_id)
    assert body.status == (
        "completed"
        if mode in {"success", "method_cap"}
        else "timed_out"
        if mode == "timeout"
        else "cancelled"
        if mode == "cancel"
        else "failed"
    )
    assert "controller.log" in body.files and "workspace.zip" in body.files
    if mode == "success":
        observed = json.loads(
            context.artifacts.read(body.files["handoff-observed.json"])
        )
        assert observed["base_url"] == settings.AI_BASE_URL
        assert observed["model"] == "scripted-agent" and observed["max_steps"] == 4
        assert (
            observed["output_tokens"] == 2000
            and observed["timeout"] == spec.policy.per_call_timeout_seconds
        )
        assert observed["prompt"].startswith(
            context.artifacts.read(spec.prompts[-1].content).decode()
        )
    assert "rm -f semflow-openhands-" in (tmp_path / "docker.log").read_text()
    assert (
        research_case.source.joinpath("app.py").read_text() == "value = eval(input())\n"
    )
    if mode in {"timeout", "cancel"}:
        calls = CallJournal(
            context.executions, spec.execution_id, spec.execution_id
        ).receipts()
        if any(row["state"] == "unknown" for row in calls):
            assert result.usage.completeness == "partial"
    shutil.rmtree(context.workspace)
    assert context.executions.inspect(spec.execution_id) == result
    member = next(iter(body.files.values()))
    path = context.artifacts.root / str(member.owner_execution_id) / member.path
    path.write_bytes(b"tampered worker artifact")
    with pytest.raises(
        Exception, match="digest|identity|integrity|changed|hash|size|reference"
    ):
        context.executions.inspect(spec.execution_id)
