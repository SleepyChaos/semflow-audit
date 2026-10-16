"""Preserve the pack-path infrastructure failure before deterministic retry."""

import argparse
import json
import shutil
from pathlib import Path

from scripts.benchmarks.mechanical_pipeline import save


def recover(root):
    base = root / "e2e"
    archive = root / "attempts/e2e-pack-path-recovery-1"
    for directory in sorted((base / "static").glob("case-*")):
        project = directory.name
        result = directory / "result.json"
        system = base / "system" / project
        if any(system.glob("*.started.json")):
            raise RuntimeError(
                "Model stage exists; refuse deterministic baseline recovery"
            )
        if result.exists():
            row = json.loads(result.read_text())
            if row.get("error") != "固定版本查询包未安装":
                continue
        elif not (directory / "started.json").exists():
            continue
        destination = archive / project
        if destination.exists():
            raise RuntimeError(
                "Duplicate recovery archive; inspect interrupted recovery"
            )
        destination.mkdir(parents=True)
        save(
            destination / "recovery-event.json",
            {
                "project_id": project,
                "reason": "CODEQL_PACK_PATH must reference installed frozen-version packs",
                "new_model_calls": 0,
                "old_deterministic_attempt_cost_retained_in_archive": True,
            },
        )
        shutil.move(str(directory), str(destination / "static"))
        if system.exists():
            shutil.move(str(system), str(destination / "system"))
    print(
        "Deterministic pack-path failures archived; ready for checkpointed retry",
        flush=True,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    recover(args.output.resolve())


if __name__ == "__main__":
    main()
