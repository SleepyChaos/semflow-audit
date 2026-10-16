"""One recorded infrastructure recovery; ordinary model failures are retained."""

import argparse
import json
import shutil
from pathlib import Path

from scripts.benchmarks.vul4py_prepare import save


def prepare(root, identity):
    directory = root / "runs" / identity
    final = directory / "result.json"
    archive = root / "attempts/infrastructure-recovery-1" / identity
    if archive.exists():
        return not final.exists()
    if not final.exists():
        return False
    row = json.loads(final.read_text())
    reason = row.get("reason", "")
    guard = reason == "Frozen implementation changed"
    generation = directory / "generation.json"
    provider = False
    if generation.exists():
        stage = json.loads(generation.read_text())["stage"]
        calls = stage.get("model_calls", [])
        provider = (
            stage["status"] == "failed"
            and bool(calls)
            and calls[-1].get("error_code")
            in {"provider_error", "rate_limited", "timeout"}
        )
    if not (guard or provider):
        return False
    archive.mkdir(parents=True)
    for path in directory.iterdir():
        if path.is_file():
            shutil.copy2(path, archive / path.name)
    save(
        archive / "recovery-event.json",
        {
            "vuln_id": identity,
            "reason": reason,
            "parent_stage_id": row.get("stage_id"),
            "strategy": "new_stage_same_inputs"
            if provider
            else "reuse_generation_if_present",
            "old_usage_retained": row.get("usage"),
            "unreceipted_inflight_call_cannot_be_excluded": provider,
        },
    )
    final.unlink()
    if provider:
        # frozen_call deliberately rejects a half-written provider invocation.
        # Preserve it and start one explicit recovery stage, never silently replay it.
        generation.unlink()
        marker = directory / "generation.started.json"
        if marker.exists():
            marker.unlink()
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    root = args.output.resolve()
    from scripts.benchmarks.realvuln_run import verify_implementation
    from scripts.benchmarks.vul4py_repair import run

    verify_implementation(root)
    config = json.loads((root / "repair-config.json").read_text())
    ids = [
        r["vuln_id"] for r in json.loads((root / "manifest.json").read_text())["cases"]
    ]
    for identity in ids:
        if prepare(root, identity):
            row = run(identity, root, config["policy"], config["image_id"])
            if row.get("stage_id"):
                stage = json.loads(
                    (root / "runs" / identity / "generation.json").read_text()
                )["stage"]
                calls = stage.get("model_calls", [])
                if (
                    stage["status"] == "failed"
                    and calls
                    and calls[-1].get("error_code")
                    in {"provider_error", "rate_limited", "timeout"}
                ):
                    raise RuntimeError(
                        "Recovery provider unavailable; receipts retained, no further paid work"
                    )


if __name__ == "__main__":
    main()
