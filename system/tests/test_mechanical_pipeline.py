"""Actual subprocess execution, durable resume and exclusive ownership."""

import json
import sys

import pytest
from scripts.benchmarks.mechanical_pipeline import exclusive, execute, validate
from scripts.benchmarks.vul4py_recover import prepare
from scripts.benchmarks.vul4py_static_recover import recover


def test_failed_step_blocks_dependents_and_resume_does_not_repeat_paid_step(tmp_path):
    plan = tmp_path / "source-plan.json"
    steps = [
        {
            "id": "one",
            "argv": [
                sys.executable,
                "-c",
                "from pathlib import Path; p=Path('paid'); p.write_text(p.read_text()+'x' if p.exists() else 'x')",
            ],
        },
        {
            "id": "two",
            "depends_on": ["one"],
            "argv": [
                sys.executable,
                "-c",
                "from pathlib import Path; import sys; sys.exit(0 if Path('recovered').exists() else 1)",
            ],
        },
        {
            "id": "three",
            "depends_on": ["two"],
            "argv": [
                sys.executable,
                "-c",
                "from pathlib import Path; Path('done').touch()",
            ],
        },
    ]
    plan.write_text(
        json.dumps(
            {
                "cwd": str(tmp_path),
                "lock_path": str(tmp_path / "shared.lock"),
                "steps": steps,
            }
        )
    )
    with pytest.raises(RuntimeError, match="two failed"):
        execute(plan, tmp_path / "run")
    assert (tmp_path / "paid").read_text() == "x"
    assert not (tmp_path / "done").exists()
    (tmp_path / "recovered").touch()
    execute(plan, tmp_path / "run")
    assert (tmp_path / "paid").read_text() == "x"
    assert (tmp_path / "done").exists()
    assert (
        json.loads((tmp_path / "run/status.json").read_text())["status"] == "completed"
    )


def test_duplicate_controller_is_rejected(tmp_path):
    with (
        exclusive(tmp_path / "lock"),
        pytest.raises(RuntimeError, match="Another pipeline"),
        exclusive(tmp_path / "lock"),
    ):
        pytest.fail("duplicate owner acquired the lock")


def test_invalid_dependency_order_is_rejected():
    with pytest.raises(ValueError, match="Dependencies"):
        validate(
            {"steps": [{"id": "second", "depends_on": ["first"], "argv": ["python"]}]}
        )


def test_recovery_keeps_provider_history_and_does_not_retry_model_failure(tmp_path):
    for identity, reason, code in [
        ("infra", "connection", "provider_error"),
        ("model", "context", "context_budget"),
    ]:
        run = tmp_path / "runs" / identity
        run.mkdir(parents=True)
        (run / "result.json").write_text(
            json.dumps(
                {"reason": reason, "stage_id": "original", "usage": {"calls": 5}}
            )
        )
        (run / "generation.json").write_text(
            json.dumps(
                {"stage": {"status": "failed", "model_calls": [{"error_code": code}]}}
            )
        )
        (run / "generation.started.json").write_text('{"stage_id":"original"}')
    assert prepare(tmp_path, "infra")
    archive = tmp_path / "attempts/infrastructure-recovery-1/infra"
    assert json.loads((archive / "result.json").read_text())["usage"] == {"calls": 5}
    assert (archive / "generation.started.json").exists()
    assert not (tmp_path / "runs/infra/generation.json").exists()
    assert not prepare(tmp_path, "model")
    assert (tmp_path / "runs/model/result.json").exists()


def test_pack_path_recovery_keeps_failed_history_and_other_outcomes(tmp_path):
    for identity, error in [
        ("case-001", "固定版本查询包未安装"),
        ("case-002", "other failure"),
    ]:
        directory = tmp_path / "e2e/static" / identity
        directory.mkdir(parents=True)
        (directory / "result.json").write_text(json.dumps({"error": error}))
    recover(tmp_path)
    assert not (tmp_path / "e2e/static/case-001").exists()
    assert (
        tmp_path / "attempts/e2e-pack-path-recovery-1/case-001/static/result.json"
    ).exists()
    assert (tmp_path / "e2e/static/case-002/result.json").exists()


def test_pack_path_recovery_refuses_model_stage(tmp_path):
    directory = tmp_path / "e2e/static/case-001"
    directory.mkdir(parents=True)
    (directory / "result.json").write_text(
        json.dumps({"error": "固定版本查询包未安装"})
    )
    system = tmp_path / "e2e/system/case-001"
    system.mkdir(parents=True)
    (system / "scout.started.json").write_text("{}")
    with pytest.raises(RuntimeError, match="Model stage exists"):
        recover(tmp_path)
    assert (directory / "result.json").exists()
