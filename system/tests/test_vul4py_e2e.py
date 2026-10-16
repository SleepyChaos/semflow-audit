"""Keep the benchmark's execution order and provider-failure boundary honest."""

import json

import pytest
from scripts.benchmarks.vul4py_e2e import main, provider_interrupted, provider_streak


def test_end_to_end_cannot_start_before_all_repair_outcomes(tmp_path, monkeypatch):
    (tmp_path / "repair-summary.json").write_text(
        json.dumps({"attempted": 99, "all_tasks_have_status": False})
    )
    monkeypatch.setattr("sys.argv", ["vul4py_e2e", "--output", str(tmp_path)])
    with pytest.raises(RuntimeError, match="all 100 repair-only"):
        main()
    assert not (tmp_path / "e2e").exists()


def test_actual_persisted_provider_failure_stops_more_paid_stages():
    receipt = {
        "stage": {
            "model_calls": [
                {"error_code": "rate_limited"},
                {"error_code": None},
            ]
        }
    }
    assert not provider_interrupted(receipt)
    receipt["stage"]["model_calls"].append({"error_code": "timeout"})
    assert provider_interrupted(receipt)
    assert not provider_interrupted({"stage": {"model_calls": []}})
    assert not provider_interrupted(
        {"stage": {"model_calls": [{"error_code": "schema_invalid"}]}}
    )


def test_isolated_provider_failure_does_not_hide_repeated_provider_outage():
    failure = {"status": "provider_interrupted", "provider_interrupted": True}
    count = provider_streak(0, failure)
    assert count == 1
    count = provider_streak(count, {"status": "input_failed"})
    assert count == 1
    count = provider_streak(count, failure)
    assert count == 2
    assert provider_streak(count, failure) == 3
    assert provider_streak(count, {"status": "partial"}) == 0
