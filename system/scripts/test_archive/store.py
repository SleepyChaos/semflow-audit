"""Store immutable result receipts and verify archived content without services."""

import hashlib
import json
import shutil
import tarfile
from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo

from .catalog import build_catalog, render_index, render_versions
from .identity import command, digest, environment, sha256
from .improvements import write_group_archives
from .relocation import file_map, resolve


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def source_inventory(root):
    tracked = command(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], root
    )
    if tracked["status"] != "observed":
        raise RuntimeError("Cannot freeze a workspace without its Git file inventory")
    names = {p for p in tracked["value"].split("\0") if p}
    names.update(
        p.relative_to(root).as_posix()
        for p in (root / "system/scripts/test_archive").glob("*.py")
    )
    names.add("system/scripts/archive_test_results.py")
    paths = sorted(
        root / name
        for name in names
        if name.startswith(
            (
                "system/backend/",
                "system/frontend/",
                "system/scripts/",
                "system/tests/",
                "system/runners/",
                ".github/",
            )
        )
        or name
        in {
            "AGENTS.md",
            "system/pyproject.toml",
            "system/uv.lock",
            "system/compose.yml",
            "system/.env.example",
        }
    )
    # Only tracked code/config or this archiver. Never traverse uploads or secret links.
    return {
        p.relative_to(root).as_posix(): sha256(p)
        for p in paths
        if p.is_file() and not p.is_symlink() and p.name != ".env"
    }


def freeze(root, archive_id, *, offline_environment=False):
    public = root / "benchmarks/testing" / archive_id
    local = root / ".local-workspace/test-archives" / archive_id
    if public.exists() or local.exists():
        raise FileExistsError(
            "Archive ID exists; choose a new ID, never overwrite a freeze"
        )
    rows = build_catalog(root)
    runtime = environment(root, inspect_images=not offline_environment)
    implementation = source_inventory(root)
    workspace_version = "WORKSPACE-" + digest(implementation)[:16]
    git_head = command(["git", "rev-parse", "HEAD"], root)
    if git_head["status"] != "observed":
        raise RuntimeError("Cannot determine Git HEAD")
    public.mkdir(parents=True)
    local.mkdir(parents=True)
    save(public / "environment.json", runtime)
    save(local / "implementation.json", implementation)
    definitions = json.loads(
        (root / "system/scripts/test_archive/improvement-versions.json").read_text()
    )
    groups = write_group_archives(public, local, archive_id, definitions, rows)
    with tarfile.open(local / "workspace-source.tar.gz", "w:gz") as bundle:
        for relative in implementation:
            bundle.add(root / relative, arcname=relative, recursive=False)
    for row in rows:
        source = root / row["path"]
        target = local / "receipts" / row["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        if sha256(source) != row["sha256"] or sha256(target) != row["sha256"]:
            raise RuntimeError("Result changed while archiving: " + row["path"])
    registry = {
        "schema_version": 1,
        "archive_id": archive_id,
        "archived_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
        "archive_timezone": "Asia/Shanghai",
        "workspace_version": workspace_version,
        "git_head_at_archive": git_head["value"],
        "working_tree_status_at_archive": command(
            ["git", "status", "--porcelain"], root
        )["value"],
        "implementation_content_sha256": digest(implementation),
        "implementation_file_count": len(implementation),
        "environment_sha256": sha256(public / "environment.json"),
        "historical_environment_inherited_from_current": False,
        "scope": "Selected result reports, summaries, run manifests/configs, integrity/version receipts root test logs and selected supplemental logs/screenshots/synthetic-input freezes",
        "excluded": "Real source uploads, full CodeQL databases/SARIF trees, per-call payloads, corpus bodies and secrets; original ignored trees retained in place",
        "id_semantics": "RES identifies path; sha256 identifies bytes; VER identifies hash-bearing evidence receipt, not a universal release; WORKSPACE identifies current source map",
        "status_counts": dict(Counter(row["version_status"] for row in rows)),
        "report_count": sum(row["role"] == "report" for row in rows),
        "local_receipt_count": sum(row["role"] == "local_receipt" for row in rows),
        "improvement_versions": groups,
        "improvement_group_counts": dict(
            Counter(row["improvement_archive_group"] for row in rows)
        ),
        "results": rows,
        "versions": [
            {
                "version_id": "VER-" + row["sha256"][:16],
                "evidence_result_id": row["result_id"],
                "evidence_path": row["path"],
                "evidence_sha256": row["sha256"],
                "evidence": row["version_evidence"],
            }
            for row in rows
            if row["version_status"] == "hash_evidence"
        ],
    }
    save(public / "registry.json", registry)
    (public / "result-index.md").write_text(render_index(archive_id, rows))
    (public / "version-index.md").write_text(
        render_versions(archive_id, registry["versions"])
    )
    checksums = {
        p.relative_to(root).as_posix(): sha256(p)
        for folder in (public, local)
        for p in folder.rglob("*")
        if p.is_file()
    }
    save(local / "archive-checksums.json", checksums)
    # Immediately verify originals, copied receipts, and every tar member against the freeze.
    problems = verify(root, archive_id, require_complete=False)
    if problems:
        raise RuntimeError("Archive validation failed: " + "; ".join(problems[:8]))
    save(
        local / "completion.json",
        {
            "archive_id": archive_id,
            "status": "complete",
            "checksums_sha256": sha256(local / "archive-checksums.json"),
        },
    )
    return {
        "archive_id": archive_id,
        "workspace_version": workspace_version,
        "report_count": registry["report_count"],
        "local_receipt_count": registry["local_receipt_count"],
        "status_counts": registry["status_counts"],
        "verification": "passed",
    }


def verify(root, archive_id, originals=True, require_complete=True):
    public = root / "benchmarks/testing" / archive_id
    local = root / ".local-workspace/test-archives" / archive_id
    problems = []
    locations = file_map(root)
    if require_complete:
        marker = local / "completion.json"
        if not marker.is_file():
            problems.append("incomplete_archive:no_completion_receipt")
        else:
            completion = json.loads(marker.read_text())
            if (
                completion.get("archive_id") != archive_id
                or completion.get("status") != "complete"
                or completion.get("checksums_sha256")
                != sha256(local / "archive-checksums.json")
            ):
                problems.append("completion_or_checksums_manifest_changed")
    checks = json.loads((local / "archive-checksums.json").read_text())
    for relative, expected in checks.items():
        path = resolve(root, relative, locations)
        if not path.is_file() or sha256(path) != expected:
            problems.append("archived_file_missing_or_changed:" + relative)
    registry = json.loads((public / "registry.json").read_text())
    ids = {row["result_id"] for row in registry["results"]}
    if len(ids) != len(registry["results"]):
        problems.append("duplicate_result_ids")
    for row in registry["results"]:
        for related in row["version_receipt_ids"] + row["related_result_ids"]:
            if related not in ids:
                problems.append("dangling_result_reference:" + related)
        if originals:
            path = resolve(root, row["path"], locations)
            if not path.is_file() or sha256(path) != row["sha256"]:
                problems.append("original_result_missing_or_changed:" + row["path"])
    implementation = json.loads((local / "implementation.json").read_text())
    if digest(implementation) != registry["implementation_content_sha256"]:
        problems.append("implementation_manifest_changed")
    with tarfile.open(local / "workspace-source.tar.gz", "r:gz") as bundle:
        members = bundle.getmembers()
        if {m.name for m in members} != set(implementation):
            problems.append("source_archive_members_changed")
        for member in members:
            stream = bundle.extractfile(member) if member.isfile() else None
            if stream is None or hashlib.file_digest(
                stream, "sha256"
            ).hexdigest() != implementation.get(member.name):
                problems.append("source_archive_content_changed:" + member.name)
    return problems
