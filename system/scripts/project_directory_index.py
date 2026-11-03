"""Read-only directory/storage inventory; never reads credentials or deletes files."""

import argparse
import csv
import hashlib
import heapq
import json
import os
import stat
import subprocess
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path


def git_paths(root, *arguments):
    output = subprocess.check_output(
        ["git", "-C", str(root), "ls-files", "-z", *arguments]
    )
    return {p.decode() for p in output.split(b"\0") if p}


def category(parts):
    if parts[0] == ".git":
        return "git_metadata"
    if parts[0] == "artifacts":
        return "audit_and_research_records"
    if parts[0] == ".local-workspace":
        return "local_workspace"
    if ".venv" in parts:
        return "python_environment"
    if "node_modules" in parts:
        return "node_dependencies"
    if set(parts) & {"__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache"}:
        return "tool_cache"
    if "dist" in parts or parts[:4] == ("system", "backend", "app", "frontend"):
        return "generated_build"
    if parts[:2] in {
        ("benchmarks", "raw"),
        ("benchmarks", "model-inputs"),
        ("benchmarks", "evaluator-only"),
    }:
        return "expanded_evaluation_inputs"
    if parts[-1] == ".DS_Store" or parts[-1].endswith(".log"):
        return "os_metadata_and_logs"
    return "project_files"


def duplicate_groups(candidates):
    groups = []
    for size, paths in candidates.items():
        if len(paths) < 2:
            continue
        digests = defaultdict(list)
        for path in paths:
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                while block := stream.read(1024 * 1024):
                    digest.update(block)
            digests[digest.hexdigest()].append(path)
        for digest, matching in digests.items():
            if len(matching) > 1:
                groups.append(
                    {
                        "sha256": digest,
                        "bytes_each": size,
                        "copies": len(matching),
                        "paths": matching,
                        "duplicate_logical_bytes": size * (len(matching) - 1),
                    }
                )
    return sorted(groups, key=lambda row: -row["duplicate_logical_bytes"])


def inventory(root):
    tracked = git_paths(root)
    untracked = git_paths(root, "--others", "--exclude-standard")
    directories, categories = defaultdict(Counter), defaultdict(Counter)
    duplicates, largest, errors, symlink_directories = defaultdict(list), [], [], []
    extra = {
        "system/backend/app",
        "system/backend/app/adapters",
        "system/backend/app/services",
        "system/backend/app/prompts",
        "system/backend/app/contracts",
        "system/frontend/src",
        "system/scripts/benchmarks",
        "system/agents/openhands/.venv",
        "system/backend/app/frontend",
    }

    def unreadable(error):
        errors.append(str(error))

    for directory, names, files in os.walk(root, followlinks=False, onerror=unreadable):
        for name in list(names):
            path = Path(directory) / name
            if path.is_symlink():
                names.remove(name)
                files.append(name)
                symlink_directories.append(path.relative_to(root).as_posix())
        for name in files:
            path = Path(directory) / name
            relative = path.relative_to(root).as_posix()
            parts = tuple(relative.split("/"))
            try:
                info = path.lstat()
            except OSError as exc:
                errors.append(str(exc))
                continue
            label = category(parts)
            state = (
                "git_metadata"
                if parts[0] == ".git"
                else (
                    "tracked"
                    if relative in tracked
                    else "untracked"
                    if relative in untracked
                    else "ignored"
                )
            )
            values = Counter(
                {
                    "files": 1,
                    "bytes": info.st_size,
                    "allocated_bytes": getattr(info, "st_blocks", 0) * 512,
                    state: 1,
                    "symlinks": int(stat.S_ISLNK(info.st_mode)),
                }
            )
            prefixes = {
                ".",
                *("/".join(parts[:n]) for n in range(1, min(3, len(parts) - 1) + 1)),
            }
            if len(parts) == 1:
                prefixes.add(relative)
            prefixes |= {p for p in extra if relative.startswith(p + "/")}
            for prefix in prefixes:
                directories[prefix].update(values)
            categories[label].update(values)
            item = (info.st_size, relative, label, state)
            if len(largest) < 60:
                heapq.heappush(largest, item)
            else:
                heapq.heappushpop(largest, item)
            if (
                state == "tracked"
                and info.st_size >= 65536
                and stat.S_ISREG(info.st_mode)
            ):
                duplicates[info.st_size].append(path)
    print(
        f"Scanned {directories['.']['files']} entries; hashing equal-size tracked candidates",
        flush=True,
    )
    matching = duplicate_groups(duplicates)
    for row in matching:
        row["paths"] = [p.relative_to(root).as_posix() for p in row["paths"]]
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "root": str(root),
        "head": subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
        ).strip(),
        "measurement": "Logical file bytes including ignored files; symlinks not followed. Not exclusive/reclaimable disk usage.",
        "tracked_paths_in_index": len(tracked),
        "untracked_visible_paths": len(untracked),
        "directories": {key: dict(value) for key, value in sorted(directories.items())},
        "categories": {key: dict(value) for key, value in sorted(categories.items())},
        "large_tracked_duplicates": matching,
        "largest_files": [
            {"bytes": size, "path": path, "category": label, "git_state": state}
            for size, path, label, state in sorted(largest, reverse=True)
        ],
        "symlink_directories_not_followed": symlink_directories,
        "errors": errors,
        "limits": [
            "No file or directory was deleted, moved or executed",
            "Only tracked, equal-size files >=64KiB were content-hashed for duplicate detection",
            "Ignore status inferred from git tracked/visible-untracked sets; nested Git metadata follows its parent category",
            "Activity, backup completeness and necessity cannot be inferred from directory size",
        ],
    }


def human_size(size):
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if size < 1024 or unit == "TiB":
            return f"{size:.2f} {unit}"
        size /= 1024


def save(result, output):
    output.mkdir(parents=True, exist_ok=True)
    (output / "inventory.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )
    fields = [
        "path",
        "files",
        "bytes",
        "allocated_bytes",
        "tracked",
        "untracked",
        "ignored",
        "git_metadata",
        "symlinks",
    ]
    with (output / "directories.csv").open("w") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, restval=0)
        writer.writeheader()
        writer.writerows(
            {"path": path, **counts} for path, counts in result["directories"].items()
        )
    print(
        json.dumps(
            {
                "total": result["directories"]["."],
                "top_level": {
                    p: v
                    for p, v in result["directories"].items()
                    if p != "." and "/" not in p
                },
                "categories": result["categories"],
                "duplicate_groups": len(result["large_tracked_duplicates"]),
                "duplicate_bytes": sum(
                    r["duplicate_logical_bytes"]
                    for r in result["large_tracked_duplicates"]
                ),
                "errors": len(result["errors"]),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[2]
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    save(inventory(args.root.resolve()), args.output.resolve())


if __name__ == "__main__":
    main()
