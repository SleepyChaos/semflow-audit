"""Inventory collected files without importing or executing third-party code."""

import csv
import hashlib
import json
import tarfile
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[3] / "benchmarks"


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def inspect(path):
    """Check transport/format, not truth of labels or runnable test correctness."""
    relative = path.relative_to(ROOT).as_posix()
    upstream_source = (
        "/source/" in relative
        or "/selected-source/" in relative
        or relative.startswith("raw/project-pairs/")
        and "/manifest.json" not in relative
        and not path.name.endswith(".tar.gz")
        or relative.startswith("raw/rules/qlcoder-b879ac2/")
        or relative.startswith("raw/rules/cwe-bench-java-spark/")
        and not path.name.endswith(".tar.gz")
    )
    if not path.stat().st_size:
        return {
            "status": "upstream_empty_file_preserved"
            if upstream_source
            else "invalid_empty"
        }
    if "failed-partial" in path.name:
        return {"status": "invalid_partial_download"}
    try:
        if path.suffix == ".json":
            value = json.loads(path.read_text())
            return {"status": "valid_json", "top_level_items": len(value)}
        if path.suffix == ".jsonl":
            rows = [
                json.loads(line)
                for line in path.read_text().splitlines()
                if line.strip()
            ]
            return {"status": "valid_jsonl", "rows": len(rows)}
        if path.suffix == ".csv":
            with path.open(newline="", encoding="utf-8-sig") as stream:
                rows = list(csv.reader(stream))
            return {"status": "valid_csv", "data_rows": max(0, len(rows) - 1)}
        if path.suffix in {".zip", ".xlsx"}:
            with zipfile.ZipFile(path) as archive:
                names = archive.namelist()
                if (
                    sum(item.file_size for item in archive.infolist())
                    > 250 * 1024 * 1024
                ):
                    return {"status": "unchecked_archive_size_limit"}
                bad = archive.testzip()
                if bad:
                    return {"status": "invalid_zip_crc", "member": bad}
                return {"status": "valid_zip_crc", "members": len(names)}
        if path.name.endswith(".tar.gz"):
            with tarfile.open(path) as archive:
                members = archive.getmembers()
                if any(
                    PurePosixPath(item.name).is_absolute()
                    or ".." in PurePosixPath(item.name).parts
                    for item in members
                ):
                    return {"status": "invalid_archive_path"}
                # Reading payloads catches truncated gzip without materializing files.
                total = sum(item.size for item in members if item.isfile())
                if total > 250 * 1024 * 1024:
                    return {"status": "unchecked_archive_size_limit"}
                for item in members:
                    if item.isfile():
                        with archive.extractfile(item) as stream:
                            while stream.read(1024 * 1024):
                                pass
                return {"status": "valid_tar_payload", "members": len(members)}
        if path.suffix == ".pdf":
            with path.open("rb") as stream:
                valid = stream.read(5) == b"%PDF-"
            return {"status": "pdf_header_only" if valid else "invalid_pdf_header"}
    except (
        ValueError,
        UnicodeError,
        OSError,
        tarfile.TarError,
        zipfile.BadZipFile,
    ) as exc:
        if upstream_source and path.suffix in {".json", ".csv"}:
            # JSONC, deliberately invalid fixtures and template JSON are source data,
            # not evidence that transport failed. Preserve them without rewriting.
            return {"status": "upstream_format_unparsed", "error": str(exc)[:200]}
        return {"status": "invalid_format", "error": str(exc)[:200]}
    return {"status": "hash_only"}


def main():
    catalogs = [
        json.loads(path.read_text())
        for path in sorted((ROOT / "catalog").glob("*.json"))
    ]
    records = []
    files = [
        path
        for folder in ("raw", "papers", "evaluator-only")
        for path in (ROOT / folder).rglob("*")
        if path.is_file()
    ]
    for path in sorted(files):
        relative = path.relative_to(ROOT).as_posix()
        sources = []
        for catalog in catalogs:
            for item in catalog["datasets"] + catalog["papers"]:
                if any(
                    relative == prefix or relative.startswith(prefix + "/")
                    for prefix in item["local_paths"]
                ):
                    sources.append(
                        {
                            "id": item["id"],
                            "url": item["official_url"],
                            "revision": item.get("version"),
                            "relationship": "catalog group; archive/member origin is preserved in raw receipts",
                        }
                    )
        records.append(
            {
                "file": relative,
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
                "sources": sources,
                "validation": inspect(path),
            }
        )
    failures = [
        row for row in records if row["validation"]["status"].startswith("invalid")
    ]
    output = {
        "date": "2026-10-05",
        "scope": "transport and format only; not oracle or benchmark execution",
        "files": records,
        "invalid_files": failures,
    }
    (ROOT / "manifests/local-integrity.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2)
    )
    pairs = json.loads((ROOT / "raw/project-pairs/manifest.json").read_text())
    targets = []
    for row in pairs["records"]:
        location = row["labels"][0]["location"]
        path = ROOT / "raw/project-pairs" / row["case_id"] / "pre" / location["file"]
        lines = (
            len(path.read_text(errors="replace").splitlines()) if path.is_file() else 0
        )
        targets.append(
            {
                "case_id": row["case_id"],
                "present": path.is_file(),
                "file_lines": lines,
                "upstream_location": location,
                "root_cause_calibration": "pending",
            }
        )
    (ROOT / "manifests/local-target-checks.json").write_text(
        json.dumps(targets, ensure_ascii=False, indent=2)
    )
    summary = {
        "collected_at": "2026-10-05",
        "stage": "collection_and_format_validation_only",
        "catalog_dataset_entries": sum(len(c["datasets"]) for c in catalogs),
        "catalog_literature_entries": sum(len(c["papers"]) for c in catalogs),
        "local_files": len(records),
        "local_bytes": sum(r["bytes"] for r in records),
        "pdf_files_including_upstream_docs": sum(
            r["file"].endswith(".pdf") for r in records
        ),
        "paper_pdf_files": sum(
            r["file"].startswith("papers/") and r["file"].endswith(".pdf")
            for r in records
        ),
        "valid_archive_files": sum(
            r["validation"]["status"] in {"valid_zip_crc", "valid_tar_payload"}
            for r in records
        ),
        "invalid_files": [
            {"file": r["file"], "status": r["validation"]["status"]} for r in failures
        ],
        "project_pairs_downloaded": sum(
            r["collection_status"] == "downloaded" for r in pairs["records"]
        ),
        "project_pairs_requested": len(pairs["records"]),
        "not_done": [
            "full prior-exposure audit",
            "model input sanitization",
            "target dependency setup",
            "security/function oracle calibration",
            "formal model evaluation",
        ],
        "runtime_tests_executed": False,
    }
    (ROOT / "manifests/collection-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2)
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
