"""Static reuse refuses changed sources, suites and failed baseline receipts."""

import json
from pathlib import Path

import pytest
from app.adapters.snapshot import snapshot_digest
from scripts.benchmarks.realvuln_static_reuse import reuse_static


def fixture(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "app.py").write_text("value = 1\n")
    previous = tmp_path / "previous"
    prior = previous / "static/demo"
    prior.mkdir(parents=True)
    (prior / "database").mkdir()
    for name in ("round-1.sarif", "execution.log"):
        (prior / name).write_text("baseline")
    pack = {"pack": "python@1", "suite": "standard"}
    config = {"codeql_cli": "2", "packs": {"python": pack}}
    (previous / "config.json").write_text(json.dumps(config))
    row = {
        "id": "demo",
        "language": "python",
        "source": str(source),
        "snapshot": snapshot_digest(source),
    }
    result = {"status": "succeeded", "snapshot": row["snapshot"], **pack}
    (prior / "result.json").write_text(json.dumps(result))
    return row, tmp_path / "new", {**config, "reuse_static_from": str(previous)}


def test_verified_reuse_links_baseline_with_explicit_receipt(tmp_path):
    row, output, config = fixture(tmp_path)
    result = reuse_static(row, output, config)
    assert result["static_not_rerun"] is True
    assert (output / "static/demo/round-1.sarif").resolve() == Path(
        config["reuse_static_from"]
    ) / "static/demo/round-1.sarif"


@pytest.mark.parametrize("change", ["source", "suite", "status"])
def test_changed_inputs_or_failure_cannot_be_reused(tmp_path, change):
    row, output, config = fixture(tmp_path)
    if change == "source":
        (Path(row["source"]) / "app.py").write_text("value = 2\n")
    elif change == "suite":
        config["packs"]["python"]["suite"] = "different"
    else:
        path = Path(config["reuse_static_from"]) / "static/demo/result.json"
        result = json.loads(path.read_text())
        result["status"] = "failed"
        path.write_text(json.dumps(result))
    with pytest.raises(RuntimeError):
        reuse_static(row, output, config)
    assert not (output / "static/demo/result.json").exists()
