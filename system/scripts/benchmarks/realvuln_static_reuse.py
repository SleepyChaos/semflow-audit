"""Verify immutable static baseline reuse for explicit incremental model retests."""

import json
from pathlib import Path

from app.adapters.snapshot import snapshot_digest
from scripts.benchmarks.realvuln_prepare import save


def read(path):
    return json.loads(path.read_text())


def reuse_static(row, output, config):
    directory = output / "static" / row["id"]
    receipt = directory / "result.json"
    if receipt.exists():
        return read(receipt)
    previous = Path(config["reuse_static_from"])
    previous_config = read(previous / "config.json")
    if (
        previous_config["codeql_cli"] != config["codeql_cli"]
        or previous_config["packs"] != config["packs"]
    ):
        raise RuntimeError("Reused CodeQL runtime or suite differs")
    prior = previous / "static" / row["id"]
    result = read(prior / "result.json")
    if (
        result["status"] != "succeeded"
        or result["snapshot"] != row["snapshot"]
        or snapshot_digest(Path(row["source"])) != row["snapshot"]
    ):
        raise RuntimeError("Reused static baseline is failed or source changed")
    pack = config["packs"][row["language"]]
    if result["pack"] != pack["pack"] or result["suite"] != pack["suite"]:
        raise RuntimeError("Reused static receipt has a different query suite")
    directory.mkdir(parents=True, exist_ok=True)
    for name in ("database", "round-1.sarif", "execution.log"):
        source = prior / name
        if not source.exists():
            raise RuntimeError(f"Missing reused static artifact: {name}")
        (directory / name).symlink_to(source, target_is_directory=source.is_dir())
    result = {**result, "baseline_reused_from": str(prior), "static_not_rerun": True}
    save(receipt, result)
    return result
