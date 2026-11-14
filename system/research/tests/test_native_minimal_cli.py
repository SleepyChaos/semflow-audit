"""The native daily command assembles and executes without platform dependencies."""

import json
from uuid import UUID

from semflow_research.public.runs import specification

from research.tests.minimal_repair_cases import cli, inputs


def test_native_minimal_command_preserves_frozen_choices_and_outputs(
    research_case, settings, tmp_path, monkeypatch
):
    original, environment, arguments = inputs(
        research_case, settings, tmp_path, monkeypatch, mode="success", engine="native"
    )
    process = cli(environment, arguments, tmp_path)
    assert process.returncode == 0, (process.stdout, process.stderr)
    result = json.loads(process.stdout)
    execution_id = UUID(json.loads(process.stderr)["execution_id"])
    request = specification(execution_id, root=research_case.ledger.root)
    assert request.inputs.engine == "native" and request.inputs.openhands is None
    assert (
        request.source == original.source
        and request.model == original.model
        and request.policy == original.policy
    )
    assert request.inputs.method_policy == original.inputs.method_policy
    assert request.inputs.validation_plan == original.inputs.validation_plan
    assert request.inputs.patch_scope == original.inputs.patch_scope
    assert (
        result["execution_status"] == "completed"
        and result["result"]["outcome"] == "checks_passed"
    )
    assert (
        result["result"]["patch"]["sha256"]
        == "688a671a08071f40df79a63b6e17045cc260e8aa2a01d08be9302842ad15b545"
    )
    assert result["usage"]["calls"] == 3
    assert result["result"]["original_snapshot_unchanged"] is True
    inspected = cli(
        environment,
        [
            "inspect",
            "--root",
            str(research_case.ledger.root),
            "--execution-id",
            str(execution_id),
        ],
        tmp_path,
    )
    assert inspected.returncode == 0 and json.loads(inspected.stdout) == result
    # The same cancellation command already serves both engines. At a terminal
    # native execution it must refuse to rewrite the published result.
    cancelled = cli(
        environment,
        [
            "cancel",
            "--root",
            str(research_case.ledger.root),
            "--execution-id",
            str(execution_id),
        ],
        tmp_path,
    )
    assert (
        cancelled.returncode == 2
        and json.loads(cancelled.stderr)["code"] == "execution_conflict"
    )
