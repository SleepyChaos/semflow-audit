"""Download exact library versions required by fixed baseline query packs."""

from pathlib import Path
import os
import subprocess
import yaml

root = Path(__file__).resolve().parents[1]
packs = root / "artifacts/packs"
versions = set()
for lock in packs.glob("codeql/*-queries/*/codeql-pack.lock.yml"):
    for name, metadata in yaml.safe_load(lock.read_text())["dependencies"].items():
        versions.add(f"{name}@{metadata['version']}")
if not versions:
    raise SystemExit("Download fixed baseline query packs first (see README)")
subprocess.run(
    ["codeql", "pack", "download", "--dir", str(packs), *sorted(versions)],
    check=True,
    env={
        key: value
        for key, value in os.environ.items()
        if key in {"PATH", "HOME", "TMPDIR"}
    },
)
