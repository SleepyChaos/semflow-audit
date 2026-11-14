"""Minimal CLI generates, decides and resumes in separate platform-free processes."""

import json
from pathlib import Path

import pytest

from research.tests.rule_cases import install_substitutes
from research.tests.rule_cli_cases import cli, inputs


@pytest.mark.parametrize(
    "approved,holdout", [(True, False), (True, True), (False, True)]
)
def test_fresh_cli_rule_control(
    research_case, settings, monkeypatch, tmp_path, approved, holdout
):
    install_substitutes(monkeypatch, [])
    env, arguments, resources = inputs(
        research_case, settings, tmp_path, holdout=holdout
    )
    generated, phases = cli(env, arguments, tmp_path)
    assert generated.returncode == 3, generated.stderr
    waiting = json.loads(generated.stdout)
    assert waiting["execution_status"] == "awaiting_input", waiting.get("failure")
    assert phases == ["inspect_semantics", "generate_rule", "fixture_validation"]
    assert waiting["result"]["outcome"] == "draft"
    root = ["--root", str(research_case.ledger.root)]
    identify = [*root, "--execution-id", waiting["execution_id"]]
    decision, phases = cli(
        env,
        [
            "decide",
            *identify,
            "--actor",
            "cli-operator",
            "--reason",
            "Reviewed exact generated positive and negative fixtures",
            *([] if approved else ["--reject"]),
        ],
        tmp_path,
    )
    assert decision.returncode == 0, decision.stderr
    assert phases == []
    command = json.loads(decision.stdout)
    assert command["approved"] is approved
    inspected, _ = cli(env, ["inspect", *identify], tmp_path)
    assert (
        json.loads(inspected.stdout) == waiting
    )  # Recording a decision never runs it.
    if approved:
        checked, phases = cli(
            env,
            [
                "rule-validate",
                *root,
                "--decision-file",
                command["decision_file"],
                "--resources",
                str(resources),
            ],
            tmp_path,
        )
        assert checked.returncode == 0, checked.stderr
        validation = json.loads(checked.stdout)
        assert validation["execution_status"] == "completed"
        assert validation["result"]["rule"] == waiting["result"]["rule"]
        assert validation["result"]["fixtures"] == waiting["result"]["fixtures"]
        assert validation["result"]["outcome"] == (
            "checks_passed" if holdout else "draft"
        )
        assert phases == ["fixture_validation"] * (2 if holdout else 1)
    continuation = [
        "resume",
        *root,
        "--decision-file",
        command["decision_file"],
        "--resources",
        str(resources),
    ]
    resumed, phases = cli(env, continuation, tmp_path)
    assert resumed.returncode == 0, resumed.stderr
    final = json.loads(resumed.stdout)
    assert final["execution_status"] == "completed", final.get("failure")
    assert final["result"]["outcome"] == (
        "needs_revision" if not approved else "checks_passed" if holdout else "draft"
    )
    assert final["result"]["rule"] == waiting["result"]["rule"]
    assert final["result"]["fixtures"] == waiting["result"]["fixtures"]
    assert final["usage"]["calls"] == waiting["usage"]["calls"] == 2
    assert phases == (
        ["fixture_validation"] * (2 if holdout else 1) if approved else []
    )
    again, phases = cli(env, continuation, tmp_path)
    assert again.returncode == 0 and json.loads(again.stdout) == final
    assert phases == []
    inspected, phases = cli(env, ["inspect", *identify], tmp_path)
    assert inspected.returncode == 0 and json.loads(inspected.stdout) == final
    assert phases == []
    assert not (research_case.ledger.root / "resources.json").exists()
    for path in (research_case.ledger.root / "artifacts").rglob("objects/*/*"):
        assert env["SEMFLOW_RULE_CLI_TEST_KEY"].encode() not in path.read_bytes()


def test_fresh_cli_rejects_stale_decision_and_missing_credentials(
    research_case, settings, monkeypatch, tmp_path
):
    install_substitutes(monkeypatch, [])
    env, arguments, resources = inputs(research_case, settings, tmp_path, holdout=False)
    generated, _ = cli(env, arguments, tmp_path)
    assert generated.returncode == 3, generated.stderr
    waiting = json.loads(generated.stdout)
    root = ["--root", str(research_case.ledger.root)]
    decision, _ = cli(
        env,
        [
            "decide",
            *root,
            "--execution-id",
            waiting["execution_id"],
            "--actor",
            "operator",
            "--reason",
            "Reviewed exact fixtures before continuation",
        ],
        tmp_path,
    )
    path = Path(json.loads(decision.stdout)["decision_file"])
    original = path.read_bytes()
    body = json.loads(original)
    body["approval"]["subject_digest"] = "0" * 64
    path.write_text(json.dumps(body))
    args = [
        "resume",
        *root,
        "--decision-file",
        str(path),
        "--resources",
        str(resources),
    ]
    rejected, phases = cli(env, args, tmp_path)
    assert (
        rejected.returncode == 2
        and json.loads(rejected.stderr)["code"] == "approval_stale"
    )
    assert phases == []
    path.write_bytes(original)
    missing = {k: v for k, v in env.items() if k != "SEMFLOW_RULE_CLI_TEST_KEY"}
    rejected, phases = cli(missing, args, tmp_path)
    assert (
        rejected.returncode == 2
        and json.loads(rejected.stderr)["code"] == "model_unavailable"
    )
    assert phases == []
    inspected, _ = cli(
        env, ["inspect", *root, "--execution-id", waiting["execution_id"]], tmp_path
    )
    assert json.loads(inspected.stdout) == waiting
    resumed, _ = cli(env, args, tmp_path)
    assert resumed.returncode == 0, resumed.stderr
