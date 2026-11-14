"""Freeze implementation inputs without copying credentials or audit artifacts."""

import argparse
import hashlib
import importlib.metadata
import json
import subprocess
import sys
import tarfile
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

SOURCE_TREES = (
    "system/backend/app",
    "system/contracts",
    "system/research",
    "system/research_cli",
    "system/tests",
    "system/scripts/benchmarks",
)
CONFIG_FILES = (
    "AGENTS.md",
    "system/pyproject.toml",
    "system/backend/pyproject.toml",
    "system/contracts/pyproject.toml",
    "system/research/pyproject.toml",
    "system/research_cli/pyproject.toml",
    "system/scripts/freeze_decoupling_baseline.py",
    "system/scripts/verify_research_install.py",
    "system/uv.lock",
    "system/compose.yml",
    "system/runners/Dockerfile.python",
)
SUFFIXES = {".py", ".txt", ".mjs", ".cjs", ".json", ".toml"}


def source_files(root: Path) -> list[Path]:
    files = {root / name for name in CONFIG_FILES if (root / name).is_file()}
    for name in SOURCE_TREES:
        for path in (root / name).rglob("*"):
            if (
                path.is_file()
                and not path.is_symlink()
                and path.suffix in SUFFIXES
                and "__pycache__" not in path.parts
                and path.resolve().is_relative_to(root)
            ):
                files.add(path)
    return sorted(files)


def git(root: Path, *arguments: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=True,
        capture_output=True,
    ).stdout


def freeze(root: Path, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    files = source_files(root)
    records = []
    archive = output / "implementation.tar.gz"
    # Read each file once; the archive and manifest always describe the same bytes.
    with tarfile.open(archive, "w:gz") as bundle:
        from io import BytesIO

        for path in files:
            data = path.read_bytes()
            name = path.relative_to(root).as_posix()
            entry = tarfile.TarInfo(name)
            entry.size, entry.mode = len(data), 0o600
            bundle.addfile(entry, BytesIO(data))
            records.append(
                {
                    "path": name,
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "size_bytes": len(data),
                }
            )
    versions = {}
    for package in ("pydantic", "langgraph", "langgraph-checkpoint", "pytest"):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = None
    manifest = {
        "schema_version": "semflow.decoupling.baseline/1",
        "baseline_id": output.name,
        "created_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
        "git_head": git(root, "rev-parse", "HEAD").decode().strip(),
        "worktree_dirty": bool(git(root, "status", "--porcelain")),
        "tracked_diff_sha256": hashlib.sha256(
            git(root, "diff", "--binary", "HEAD", "--", *SOURCE_TREES, *CONFIG_FILES)
        ).hexdigest(),
        "python": sys.version.split()[0],
        "installed_versions": versions,
        "archive": archive.name,
        "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "files": records,
        "excluded": [".env*", "credentials", "uploaded projects", "audit artifacts"],
        "external_resources": {
            "status": "not_attested",
            "meaning": "CodeQL packs, images, corpus and model identity need per-run receipts",
        },
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[2]
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    identifier = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y%m%dT%H%M%S")
    output = args.output or root / "artifacts/decoupling/baselines" / (
        identifier + "-" + uuid4().hex[:8]
    )
    manifest = freeze(root, output)
    print(
        json.dumps(
            {
                "baseline_id": manifest["baseline_id"],
                "manifest": str(output / "manifest.json"),
                "archive_sha256": manifest["archive_sha256"],
                "files": len(manifest["files"]),
            }
        )
    )


if __name__ == "__main__":
    main()
