"""Full performance execution must not silently skip invalid-oracle projects."""

import json

import pytest
from scripts.benchmarks import vul4py_repair
from scripts.benchmarks.vul4py_performance import summarize


@pytest.mark.parametrize("enabled", [False, True])
def test_uncalibrated_generation_requires_explicit_policy(
    tmp_path, monkeypatch, enabled
):
    folder = tmp_path / "calibration" / "sample"
    folder.mkdir(parents=True)
    (folder / "result.json").write_text(json.dumps({"accepted": False}))
    (tmp_path / "repair-config.json").write_text(
        json.dumps({"generate_uncalibrated": enabled})
    )
    attempted = []
    monkeypatch.setattr(vul4py_repair, "verify_implementation", lambda _: None)

    def unavailable(identity, output):
        attempted.append(identity)
        raise RuntimeError("source unavailable; not a successful empty repair")

    monkeypatch.setattr(vul4py_repair, "register", unavailable)
    result = vul4py_repair.run("sample", tmp_path, {}, "test-image")
    assert attempted == (["sample"] if enabled else [])
    assert result["oracle_eligible"] is False
    assert result["joint_pass"] is False
    assert result["status"] == ("repair_failed" if enabled else "not_evaluated")


def test_performance_ledger_keeps_unscored_and_failure_in_denominator(tmp_path):
    for name, status in [("one", "generated_unscored"), ("two", "repair_failed")]:
        folder = tmp_path / "runs" / name
        folder.mkdir(parents=True)
        (folder / "result.json").write_text(
            json.dumps({"status": status, "oracle_eligible": False})
        )
        (folder / "generation.json").write_text(
            json.dumps(
                {
                    "wall_seconds": 12,
                    "stage": {
                        "usage": {"calls": 3, "input_tokens": 100, "output_tokens": 10}
                    },
                }
            )
        )
    summary = summarize(tmp_path, ["one", "two", "pending"])
    assert summary["planned"] == 3 and summary["terminal"] == 2
    assert summary["scored"] == summary["joint_pass"] == 0
    assert summary["calls"] == 6 and summary["input_tokens"] == 200
    assert summary["repair_stage_seconds_p95"] == 12
