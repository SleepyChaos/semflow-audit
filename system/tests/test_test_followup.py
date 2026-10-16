"""Completion must come from the controller and complete, consistent receipts."""

import json

import pytest
from scripts.benchmarks import cqllm_results, pipeline_wait
from scripts.benchmarks.vul4py_followup_prepare import prepare


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


def test_wait_does_not_treat_dead_controller_as_completed(tmp_path, monkeypatch):
    monkeypatch.setattr(
        pipeline_wait, "observe", lambda _: {"status": "controller_exited"}
    )
    with pytest.raises(RuntimeError, match="attention"):
        pipeline_wait.check(tmp_path)
    monkeypatch.setattr(pipeline_wait, "observe", lambda _: {"status": "running"})
    assert pipeline_wait.check(tmp_path)[0] is False


def matrix(root):
    write(
        root / "manifest.json",
        {
            "arms": ["current_rag"],
            "tasks": [{"id": "row-0001"}],
            "scope": "fixture",
        },
    )
    directory = root / "arms/current_rag/row-0001"
    write(
        directory / "result.json",
        {
            "arm": "current_rag",
            "task_id": "row-0001",
            "status": "compiled",
            "compile_success": True,
            "first_compile_success": False,
        },
    )
    write(
        directory / "evaluation.json",
        {
            "arm": "current_rag",
            "task_id": "row-0001",
            "status": "executed",
            "execution_success": True,
            "alerts": 0,
        },
    )
    write(
        directory / "model-calls.json",
        {
            "records": [
                {"input_tokens": 10, "output_tokens": 5},
                {"input_tokens": None, "output_tokens": None},
            ]
        },
    )
    return directory


def test_report_preserves_unknown_usage_and_zero_alert_semantic_unknown(tmp_path):
    matrix(tmp_path)
    summary = cqllm_results.export(tmp_path, tmp_path / "report")
    assert summary["arms"]["current_rag"]["execution_pass"] == 1
    assert summary["arms"]["current_rag"]["unknown_usage_calls"] == 1
    assert summary["arms"]["current_rag"]["known_input_tokens"] == 10
    table = (tmp_path / "report/tasks.csv").read_text()
    assert "semantic_correct" in table
    assert "checksums.json" not in json.loads(
        (tmp_path / "report/checksums.json").read_text()
    )


def test_incomplete_or_mismatched_receipt_cannot_unlock_followup(tmp_path):
    directory = matrix(tmp_path)
    (directory / "evaluation.json").unlink()
    with pytest.raises(RuntimeError, match="Incomplete"):
        cqllm_results.reconcile(tmp_path)
    write(directory / "evaluation.json", {"arm": "no_rag", "task_id": "row-0001"})
    with pytest.raises(RuntimeError, match="identity"):
        cqllm_results.reconcile(tmp_path)


def test_partial_freeze_never_silently_reuses_inputs(tmp_path):
    output = tmp_path / "new"
    output.mkdir()
    (output / "manifest.json").write_text("{}")
    with pytest.raises(RuntimeError, match="explicit recovery"):
        prepare(tmp_path / "old", output)
