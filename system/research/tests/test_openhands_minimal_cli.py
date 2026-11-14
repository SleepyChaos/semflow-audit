"""Independent minimal CLI assembles mechanical contracts and controls a worker."""

import json
import subprocess
import sys
import time

from semflow_research.public.runs import specification

from research.tests.minimal_repair_cases import cli, inputs
from research.tests.repair_cli_cases import SCRIPT


def test_minimal_openhands_cli_run_inspect_without_platform(
    research_case, settings, tmp_path, monkeypatch
):
    original, env, args = inputs(
        research_case, settings, tmp_path, monkeypatch, mode="success"
    )
    result = cli(env, args, tmp_path)
    assert result.returncode == 0, (result.stdout, result.stderr)
    body = json.loads(result.stdout)
    identifier = json.loads(result.stderr)["execution_id"]
    assert identifier == body["execution_id"]
    assert (
        body["execution_status"] == "completed"
        and body["result"]["outcome"] == "checks_passed"
    )
    from uuid import UUID

    frozen = specification(UUID(identifier), root=research_case.ledger.root)
    assert frozen.inputs.openhands == original.inputs.openhands
    assert frozen.inputs.method_policy == original.inputs.method_policy
    assert frozen.inputs.validation_plan == original.inputs.validation_plan
    assert (
        frozen.source == original.source
        and frozen.model == original.model
        and frozen.policy == original.policy
    )
    assert any(
        row["provider"] == "openhands/openai-compatible"
        for row in body["usage"]["by_provider"]
    )
    inspected = cli(
        env,
        [
            "inspect",
            "--root",
            str(research_case.ledger.root),
            "--execution-id",
            identifier,
        ],
        tmp_path,
    )
    assert inspected.returncode == 0 and json.loads(inspected.stdout) == body


def test_minimal_openhands_cli_cancel_joins_worker_and_retains_receipt(
    research_case, settings, tmp_path, monkeypatch
):
    _, env, args = inputs(research_case, settings, tmp_path, monkeypatch, mode="cancel")
    process = subprocess.Popen(
        [sys.executable, "-c", SCRIPT, *args],
        cwd=tmp_path,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        prepared = json.loads(process.stderr.readline())
        identifier = prepared["execution_id"]
        calls = (
            research_case.ledger.root / "workspaces" / identifier / "openhands/calls"
        )
        deadline = time.monotonic() + 15
        while (
            not list(calls.glob("*.response.json"))
            and process.poll() is None
            and time.monotonic() < deadline
        ):
            time.sleep(0.05)
        assert list(calls.glob("*.response.json")), process.communicate(timeout=5)
        cancelled = cli(
            env,
            [
                "cancel",
                "--root",
                str(research_case.ledger.root),
                "--execution-id",
                identifier,
            ],
            tmp_path,
        )
        assert cancelled.returncode == 0, cancelled.stderr
        output, error = process.communicate(timeout=15)
        assert process.returncode == 130, (output, error)
        body = json.loads(output)
        assert (
            body["execution_status"] == "cancelled"
            and body["failure"]["detail"]["schema_version"]
            == "semflow.openhands-receipt/1"
        )
        assert body["usage"]["completeness"] == "partial"
        assert "rm -f semflow-openhands-" in (tmp_path / "docker.log").read_text()
    finally:
        if process.poll() is None:
            process.terminate()
            process.communicate(timeout=15)
