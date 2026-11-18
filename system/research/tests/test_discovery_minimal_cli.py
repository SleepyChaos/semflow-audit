"""The four discovery operations run through one public kernel in fresh processes."""

import json
import os
from pathlib import Path
from uuid import UUID

import pytest
from research.tests.discovery_cli_cases import make_files, run
from semflow_research.public.baselines import for_execution
from semflow_research.public.runs import specification


@pytest.mark.parametrize(
    "command", ["discovery-scan", "discovery-scout", "discovery-discover"]
)
def test_discovery_minimal_cli_operations_without_platform_imports(
    research_case, settings, tmp_path, command
):
    resources, options = make_files(research_case, settings, tmp_path)
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("AI_", "DATABASE_", "REDIS_", "PROJECT_"))
    }
    system = Path(__file__).resolve().parents[2]
    env["PYTHONPATH"] = os.pathsep.join(
        str(system / name)
        for name in ("contracts/src", "research/src", "research_cli/src")
    )
    result = run(
        env,
        [
            command,
            "--root",
            str(research_case.ledger.root),
            "--source-directory",
            str(research_case.source),
            "--options",
            str(options),
            "--resources",
            str(resources),
            "--dependency-lock",
            str(system / "uv.lock"),
        ],
        tmp_path,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    payload = json.loads(result.stdout)
    assert payload["execution_status"] == "completed", payload.get("failure")
    assert payload["module"] == "discovery" and payload[
        "operation"
    ] == command.removeprefix("discovery-")
    if command == "discovery-scan":
        assert payload["result"]["baseline"] is not None
    else:
        assert payload["result"]["candidates"] is not None


@pytest.mark.parametrize("upstream_command", ["discovery-scan", "discovery-discover"])
def test_discovery_review_cli_consumes_frozen_upstream_bundle(
    research_case, settings, tmp_path, upstream_command
):
    resources, options = make_files(research_case, settings, tmp_path)
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("AI_", "DATABASE_", "REDIS_", "PROJECT_"))
    }
    system = Path(__file__).resolve().parents[2]
    env["PYTHONPATH"] = os.pathsep.join(
        str(system / name)
        for name in ("contracts/src", "research/src", "research_cli/src")
    )
    scan = run(
        env,
        [
            upstream_command,
            "--root",
            str(research_case.ledger.root),
            "--source-directory",
            str(research_case.source),
            "--options",
            str(options),
            "--resources",
            str(resources),
            "--dependency-lock",
            str(system / "uv.lock"),
        ],
        tmp_path,
    )
    assert scan.returncode == 0, scan.stderr
    upstream = json.loads(scan.stdout)["execution_id"]
    review = run(
        env,
        [
            "discovery-review",
            "--root",
            str(research_case.ledger.root),
            "--upstream-execution-id",
            upstream,
            "--options",
            str(options),
            "--resources",
            str(resources),
            "--dependency-lock",
            str(system / "uv.lock"),
        ],
        tmp_path,
    )
    assert review.returncode == 0, review.stderr + review.stdout
    payload = json.loads(review.stdout)
    assert payload["execution_status"] == "completed"
    assert payload["result"]["assessments"] is not None
    report = run(
        env,
        [
            "discovery-review-report",
            "--root",
            str(research_case.ledger.root),
            "--execution-id",
            payload["execution_id"],
        ],
        tmp_path,
    )
    assert report.returncode == 0, report.stderr + report.stdout
    rows = json.loads(report.stdout)
    assert rows["report"]["records"]
    assert rows["cache"] is None
    if upstream_command == "discovery-scan":
        candidate = rows["report"]["records"][0]["candidate_ref"]["entity_id"]
        for mode in ([], ["--without-cache"]):
            continued = run(
                env,
                [
                    "discovery-review-continue",
                    "--root",
                    str(research_case.ledger.root),
                    "--upstream-execution-id",
                    payload["execution_id"],
                    "--candidate-id",
                    candidate,
                    "--resources",
                    str(resources),
                    "--dependency-lock",
                    str(system / "uv.lock"),
                    *mode,
                ],
                tmp_path,
            )
            assert continued.returncode == 0, continued.stderr + continued.stdout
            receipt = json.loads(continued.stdout)
            assert receipt["execution_status"] == "completed", receipt["failure"]
            from semflow_research.public.discovery_results import read_result

            current = read_result(
                UUID(receipt["execution_id"]), root=research_case.ledger.root
            )
            assert current.review_cache.mode == ("reread" if mode else "reuse")
            assert current.assessments[0].conclusion == "insufficient"

    # A review produces assessments, not a new scan; downstream replay/rescan
    # must still select its original immutable baseline without caller-written refs.
    selected = for_execution(
        UUID(payload["execution_id"]), root=research_case.ledger.root
    )
    assert selected is not None
    assert (
        selected
        == specification(
            UUID(payload["execution_id"]), root=research_case.ledger.root
        ).inputs.baseline
    )


def test_discovery_cli_cancel_and_inspect_preserve_terminal_receipt(
    research_case, settings, tmp_path
):
    resources, options = make_files(research_case, settings, tmp_path)
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("AI_", "DATABASE_", "REDIS_", "PROJECT_"))
    }
    system = Path(__file__).resolve().parents[2]
    env["PYTHONPATH"] = os.pathsep.join(
        str(system / name)
        for name in ("contracts/src", "research/src", "research_cli/src")
    )
    result = run(
        env,
        [
            "discovery-scan",
            "--root",
            str(research_case.ledger.root),
            "--source-directory",
            str(research_case.source),
            "--options",
            str(options),
            "--resources",
            str(resources),
            "--dependency-lock",
            str(system / "uv.lock"),
        ],
        tmp_path,
    )
    payload = json.loads(result.stdout)
    inspect = run(
        env,
        [
            "inspect",
            "--root",
            str(research_case.ledger.root),
            "--execution-id",
            payload["execution_id"],
        ],
        tmp_path,
    )
    assert inspect.returncode == 0 and json.loads(inspect.stdout) == payload
    cancelled = run(
        env,
        [
            "cancel",
            "--root",
            str(research_case.ledger.root),
            "--execution-id",
            payload["execution_id"],
        ],
        tmp_path,
    )
    assert cancelled.returncode == 2
    assert json.loads(cancelled.stderr)["code"] == "execution_conflict"
