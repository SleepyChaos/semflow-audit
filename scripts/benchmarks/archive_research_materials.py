"""Package public research inputs without executing them or changing local originals."""

import argparse
import gzip
import hashlib
import io
import json
import re
import tarfile
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
BENCH = ROOT / "benchmark-data"
MANIFEST = BENCH / "manifests/repository-datasets.json"
BLOCKED_PARTS = {".git", "node_modules", "__pycache__", ".venv", ".pytest_cache"}
SECRET = re.compile(
    rb"-----BEGIN (?:RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY-----"
    rb"|(?<![A-Za-z0-9_])gh[pousr]_[A-Za-z0-9]{36,}"
    rb"|(?<![A-Za-z0-9_])github_pat_[A-Za-z0-9_]{60,}"
    rb"|(?<![A-Za-z0-9_])sk-(?:proj-)?[A-Za-z0-9_-]{40,}"
)
PRIVATE_BLOCK = re.compile(
    rb"-----BEGIN ((?:RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY)-----"
    rb".*?-----END \1-----",
    re.DOTALL,
)


def public_copy(name, data):
    """Redact embedded test credentials, retaining the surrounding task records."""
    if name.endswith((".zip", ".xlsx", ".docx", ".tar.gz", ".tgz", ".tar")):
        return data, 0
    sanitized, blocks = PRIVATE_BLOCK.subn(b"[REDACTED_PRIVATE_KEY]", data)
    sanitized, markers = SECRET.subn(b"[REDACTED_CREDENTIAL]", sanitized)
    if (blocks or markers) and name.endswith(".json"):
        json.loads(sanitized)
    return sanitized, blocks + markers


def digest(data):
    return hashlib.sha256(data).hexdigest()


def path_reason(name):
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts:
        return "unsafe_path"
    if set(path.parts) & BLOCKED_PARTS:
        return "local_dependency_or_git_state"
    if path.name == ".DS_Store" or path.name.startswith((".~", "~$")):
        return "editor_or_os_metadata"
    if (
        path.name == ".env"
        or path.name.startswith(".env.")
        and path.name != ".env.example"
    ):
        return "local_environment"
    if path.suffix in {".key", ".p12", ".pfx", ".sarif", ".log", ".pyc"}:
        return "key_or_execution_artifact"
    if "failed-partial" in path.name:
        return "failed_partial_download"
    return None


def transport_reason(name, data, depth=0):
    """Inspect nested transport archives; never extract or run upstream files."""
    if SECRET.search(data):
        return "credential_pattern"
    is_zip = name.endswith((".zip", ".xlsx", ".docx"))
    is_tar = name.endswith((".tar.gz", ".tgz", ".tar"))
    if not (is_zip or is_tar):
        return None
    if depth >= 5:
        return "nested_archive_depth_limit"
    try:
        if is_zip:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                for item in archive.infolist():
                    reason = path_reason(item.filename)
                    if reason:
                        return "archive_contains_" + reason
                    if item.file_size > 100 * 1024 * 1024:
                        return "archive_member_size_limit"
                    if not item.is_dir():
                        reason = transport_reason(
                            item.filename, archive.read(item), depth + 1
                        )
                        if reason:
                            return "archive_contains_" + reason
        else:
            with tarfile.open(fileobj=io.BytesIO(data), mode="r:*") as archive:
                for item in archive:
                    reason = path_reason(item.name)
                    if reason:
                        return "archive_contains_" + reason
                    if (
                        item.issym()
                        or item.islnk()
                        or not (item.isdir() or item.isfile())
                    ):
                        return "archive_special_member"
                    if item.size > 100 * 1024 * 1024:
                        return "archive_member_size_limit"
                    if item.isfile():
                        with archive.extractfile(item) as stream:
                            reason = transport_reason(
                                item.name, stream.read(), depth + 1
                            )
                        if reason:
                            return "archive_contains_" + reason
    except (OSError, ValueError, tarfile.TarError, zipfile.BadZipFile, RuntimeError):
        return "invalid_transport_archive"
    return None


def groups():
    for direction in ("discovery", "rules", "repair", "project-pairs"):
        directory = BENCH / "raw" / direction
        loose = []
        for path in sorted(directory.iterdir()):
            if path.is_dir() and not path.is_symlink():
                prefix = "raw/" + direction + "/" + path.name
                if direction == "project-pairs":
                    pair_loose = []
                    for child in sorted(path.iterdir()):
                        if child.is_dir() and not child.is_symlink():
                            yield prefix + "/" + child.name, sorted(child.rglob("*"))
                        else:
                            pair_loose.append(child)
                    yield prefix + "/standalone", pair_loose
                else:
                    yield prefix, sorted(path.rglob("*"))
            else:
                loose.append(path)
        if loose:
            yield "raw/" + direction + "/standalone", loose
    for name in ("evaluator-only", "model-inputs"):
        yield name, sorted((BENCH / name).rglob("*"))


def build():
    prior = json.loads((BENCH / "manifests/local-integrity.json").read_text())
    invalid = {
        row["file"]: row["validation"]["status"]
        for row in prior["files"]
        if row["validation"]["status"].startswith("invalid")
    }
    inventory = json.loads(
        (BENCH / "manifests/current-test-inventory.json").read_text()
    )
    result = {
        "schema_version": 1,
        "archived_on": "2026-10-11",
        "scope": "Previously collected public inputs; transport integrity, not benchmark success",
        "restore_base": "benchmark-data",
        "datasets": inventory["datasets"],
        "bundles": [],
        "excluded": [],
        "redactions": [],
    }
    for group, paths in groups():
        destination = BENCH / "datasets" / (group + ".tar.gz")
        destination.parent.mkdir(parents=True, exist_ok=True)
        records = []
        with (
            destination.open("wb") as output,
            gzip.GzipFile(
                filename="", mode="wb", fileobj=output, mtime=0
            ) as compressed,
            tarfile.open(fileobj=compressed, mode="w|") as archive,
        ):
            for path in paths:
                if path.is_dir() and not path.is_symlink():
                    continue
                name = path.relative_to(BENCH).as_posix()
                reason = (
                    "symlink_not_published" if path.is_symlink() else path_reason(name)
                )
                reason = reason or invalid.get(name)
                data = b"" if reason else path.read_bytes()
                original_sha256 = digest(data)
                data, redactions = public_copy(name, data)
                reason = reason or transport_reason(name, data)
                if reason:
                    result["excluded"].append({"path": name, "reason": reason})
                    continue
                if redactions:
                    result["redactions"].append(
                        {
                            "path": name,
                            "original_sha256": original_sha256,
                            "published_sha256": digest(data),
                            "replacement_count": redactions,
                            "reason": "embedded_test_credentials_removed; not a pristine upstream copy",
                        }
                    )
                info = tarfile.TarInfo(name)
                info.size = len(data)
                info.mode = 0o755 if path.stat().st_mode & 0o111 else 0o644
                archive.addfile(info, io.BytesIO(data))
                records.append(
                    {"path": name, "bytes": len(data), "sha256": digest(data)}
                )
        data = destination.read_bytes()
        if len(data) >= 100 * 1024 * 1024:
            raise ValueError(f"Bundle exceeds repository file limit: {destination}")
        result["bundles"].append(
            {
                "path": destination.relative_to(ROOT).as_posix(),
                "bytes": len(data),
                "sha256": digest(data),
                "files": records,
            }
        )
        print(f"Packed {group}: {len(records)} files, {len(data)} bytes", flush=True)
    result["summary"] = {
        "bundle_count": len(result["bundles"]),
        "file_count": sum(len(row["files"]) for row in result["bundles"]),
        "input_bytes": sum(f["bytes"] for b in result["bundles"] for f in b["files"]),
        "compressed_bytes": sum(row["bytes"] for row in result["bundles"]),
        "excluded_file_count": len(result["excluded"]),
        "redacted_file_count": len(result["redactions"]),
    }
    MANIFEST.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return result


def verify_or_restore(manifest, restore=False):
    count = 0
    seen = set()
    for bundle in manifest["bundles"]:
        path = ROOT / bundle["path"]
        data = path.read_bytes()
        if len(data) != bundle["bytes"] or digest(data) != bundle["sha256"]:
            raise ValueError(f"Bundle checksum mismatch: {path}")
        expected = {row["path"]: row for row in bundle["files"]}
        found = set()
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
            for member in archive:
                name = member.name
                if (
                    not member.isfile()
                    or path_reason(name)
                    or name in seen
                    or name not in expected
                ):
                    raise ValueError(f"Unexpected archive member: {name}")
                with archive.extractfile(member) as stream:
                    payload = stream.read()
                row = expected[name]
                if len(payload) != row["bytes"] or digest(payload) != row["sha256"]:
                    raise ValueError(f"Member checksum mismatch: {name}")
                if transport_reason(name, payload):
                    raise ValueError(f"Blocked payload: {name}")
                target = BENCH / name
                if restore:
                    if (
                        target.is_symlink()
                        or BENCH.resolve() not in target.resolve().parents
                    ):
                        raise ValueError(f"Unsafe restoration path: {name}")
                    if target.exists():
                        if (
                            not target.is_file()
                            or digest(target.read_bytes()) != row["sha256"]
                        ):
                            raise ValueError(
                                f"Existing input differs; refusing overwrite: {name}"
                            )
                    else:
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(payload)
                        target.chmod(member.mode & 0o777)
                found.add(name)
                seen.add(name)
                count += 1
        if found != expected.keys():
            raise ValueError(f"Missing archive members: {path}")
    print(
        json.dumps(
            {
                "verified_files": count,
                "bundles": len(manifest["bundles"]),
                "restored": restore,
                "summary": manifest["summary"],
            },
            ensure_ascii=False,
        )
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--build", action="store_true", help="Package existing local originals"
    )
    parser.add_argument(
        "--restore",
        action="store_true",
        help="Verify and restore missing inputs; never overwrite",
    )
    args = parser.parse_args()
    if args.build and args.restore:
        parser.error("Choose --build or --restore")
    manifest = build() if args.build else json.loads(MANIFEST.read_text())
    verify_or_restore(manifest, args.restore)


if __name__ == "__main__":
    main()
