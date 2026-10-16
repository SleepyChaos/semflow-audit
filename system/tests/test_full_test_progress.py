"""Do not advance a paid experiment based on terminal-count shortcuts."""

import json

from scripts.benchmarks.full_test_progress import collect, receipts


def save(path, row):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(row))


def test_receipts_reject_cross_task_invalid_and_unexpected(tmp_path):
    save(tmp_path / "one/result.json", {"vuln_id": "other", "status": "evaluated"})
    save(tmp_path / "extra/result.json", {"vuln_id": "extra", "status": "evaluated"})
    status, rows = receipts(tmp_path, ["one", "two"])
    assert not status["all_have_receipts"]
    assert status["missing"] == ["two"]
    assert len(status["invalid"]) == 1
    assert status["unexpected"] == ["extra"]
    assert rows == {}


def test_terminal_count_cannot_hide_infrastructure_interruption(tmp_path):
    root = tmp_path / "vul4py/batch"
    ids = [f"task-{i}" for i in range(100)]
    save(root / "manifest.json", {"cases": [{"vuln_id": i} for i in ids]})
    save(root / "implementation-hashes.json", {})
    save(
        root / "e2e/inputs.json",
        {"records": [{"id": i, "status": "prepared"} for i in ids]},
    )
    for identity in ids:
        save(
            root / f"calibration/{identity}/result.json",
            {
                "vuln_id": identity,
                "status": "accepted",
                "accepted": True,
            },
        )
        save(
            root / f"runs/{identity}/result.json",
            {
                "vuln_id": identity,
                "status": "evaluated",
                "joint_pass": False,
            },
        )
    save(
        root / f"runs/{ids[0]}/generation.json",
        {
            "stage": {
                "status": "failed",
                "model_calls": [{"error_code": "provider_error"}],
            },
        },
    )
    result = collect(root)
    assert result["known_location_repair"]["records"] == 100
    assert not result["known_location_repair"]["ready_for_e2e"]
    assert result["known_location_repair"]["recovery_required"][
        "provider_interrupted"
    ] == [ids[0]]
    assert result["end_to_end"]["records"] == 0
