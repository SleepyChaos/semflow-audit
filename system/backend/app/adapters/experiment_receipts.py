"""Version fingerprints and durable receipts, without copying source or credentials."""

import hashlib
import json
import platform
import subprocess
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from app.adapters.artifacts import ArtifactStore
from app.models import get_datetime_utc
from app.services.report_materials import redact


def digest(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def implementation_stamp() -> dict:
    package = Path(__file__).resolve().parents[1]
    files = {
        path.relative_to(package).as_posix(): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in sorted(package.rglob("*"))
        if path.is_file()
        and path.suffix in {".py", ".txt"}
        and "__pycache__" not in path.parts
    }
    stamp = {
        "source_tree_sha256": digest(files),
        "source_files": files,
        "python": platform.python_version(),
    }
    system = package.parents[1]
    stamp["dependency_files"] = {
        name: hashlib.sha256((system / name).read_bytes()).hexdigest()
        for name in ("uv.lock", "pyproject.toml", "backend/pyproject.toml")
        if (system / name).is_file()
    }
    dependencies = {}
    for name in [
        "langgraph",
        "langgraph-checkpoint-postgres",
        "sqlmodel",
        "psycopg",
        "openai",
        "haystack-ai",
    ]:
        try:
            dependencies[name] = version(name)
        except PackageNotFoundError:
            dependencies[name] = None
    stamp["dependencies"] = dependencies
    try:

        def git(*args):
            return subprocess.check_output(
                ["git", "-C", str(package), *args],
                stderr=subprocess.DEVNULL,
                timeout=10,
            )

        stamp["git_commit"] = git("rev-parse", "HEAD").decode().strip()
        stamp["git_dirty"] = bool(git("status", "--porcelain"))
        stamp["tracked_diff_sha256"] = hashlib.sha256(
            git("diff", "--binary", "HEAD")
        ).hexdigest()
    except OSError, subprocess.SubprocessError:
        stamp["git_commit"] = None
    return stamp


class ExperimentReceipt:
    def __init__(self, identifier: str):
        self.identifier = identifier
        self.directory = ArtifactStore().directory(identifier)

    def start(self, payload: dict):
        with (self.directory / "experiment-input.json").open(
            "x", encoding="utf-8"
        ) as stream:
            json.dump(redact(payload), stream, ensure_ascii=False, indent=2)
        self.event("created", {"input_sha256": digest(redact(payload))})

    def event(self, name: str, payload: dict):
        row = redact({"event": name, "at": get_datetime_utc().isoformat(), **payload})
        with (self.directory / "execution-events.jsonl").open(
            "a", encoding="utf-8"
        ) as stream:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")

    def save(self, payload: dict):
        path = self.directory / "execution-receipt.json"
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(redact(payload), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        temporary.replace(path)


def execution_record(row) -> dict:
    data = row.model_dump(mode="json")
    identifier = str(row.id)
    return {
        **data,
        "artifacts": str(ArtifactStore().directory(identifier)),
        "checkpoint_thread_id": identifier,
    }
