"""Freeze selection before scans; collect full snapshots without running upstream code."""

import argparse
import csv
import hashlib
import io
import json
import tarfile
import urllib.request
from pathlib import Path, PurePosixPath
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
MATERIALS = ROOT / "artifacts/research-materials"


def choose():
    javascript = []
    with tarfile.open(MATERIALS / "ossf-benchmark.tar.gz") as bundle:
        for item in bundle.getmembers():
            if not item.isfile() or not item.name.endswith(".json"):
                continue
            try:
                row = json.load(bundle.extractfile(item))
            except (ValueError, UnicodeError):
                continue
            if isinstance(row, dict) and "repository" in row and "prePatch" in row:
                locations = row["prePatch"].get("weaknesses", [])
                if locations and all(
                    w["location"]["file"].endswith((".js", ".ts")) for w in locations
                ):
                    javascript.append(
                        {
                            "cve": row["CVE"],
                            "repository": row["repository"],
                            "pre_commit": row["prePatch"]["commit"],
                            "post_commit": row["postPatch"]["commit"],
                            "labels": locations,
                            "cwes": row.get("CWEs", []),
                            "language": "javascript",
                            "source": "OpenSSF fixed archive",
                            "label_status": "upstream_unadjudicated",
                        }
                    )
    python = [
        {
            "cve": r["vuln_id"],
            "repository": r["repo_url"],
            "post_commit": r["fix_commit"],
            "language": "python",
            "source": "Vul4Py fixed CSV",
            "label_status": "fix_index_only",
        }
        for r in csv.DictReader((MATERIALS / "vul4py.csv").open())
    ]
    selected = []
    for rows in (javascript, python):
        seen = set()
        # Descending advisory ID, one case per repository, no detector scores.
        for row in sorted(rows, key=lambda r: r["cve"], reverse=True):
            if row["repository"] in seen:
                continue
            seen.add(row["repository"])
            selected.append(
                {
                    **row,
                    "case_id": str(uuid4()),
                    "split": "pilot_development",
                    "oracle_status": "not_validated",
                }
            )
            if len(seen) == 10:
                break
    return selected


def fetch(url, limit=100 * 1024 * 1024):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "ai-code-audit-research",
            "Accept": "application/vnd.github+json",
        },
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        content = response.read(limit + 1)
        if len(content) > limit:
            raise ValueError("download size limit exceeded")
        return content


def unpack(content, root):
    total = count = 0
    with tarfile.open(fileobj=io.BytesIO(content), mode="r:gz") as bundle:
        for item in bundle.getmembers():
            relative = PurePosixPath(item.name)
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("archive path invalid")
            if item.isdir():
                continue
            if len(relative.parts) < 2:
                raise ValueError("archive path invalid")
            if not item.isfile():
                # Symlinks are preserved in archive provenance but never followed.
                continue
            path = root.joinpath(*relative.parts[1:])
            total += item.size
            count += 1
            if total > 100 * 1024 * 1024 or count > 20000:
                raise ValueError("extracted snapshot limit exceeded")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(bundle.extractfile(item).read())
    return {"files": count, "bytes": total, "symlinks": "not materialized"}


def collect(output, row):
    directory = output / row["case_id"]
    directory.mkdir(exist_ok=True)
    repository = (
        row["repository"].removesuffix(".git").removeprefix("https://github.com/")
    )
    commit_url = (
        f"https://api.github.com/repos/{repository}/commits/{row['post_commit']}"
    )
    if row["language"] == "python":
        metadata_path = directory / "fix-commit-evaluator.json"
        metadata = (
            metadata_path.read_bytes()
            if metadata_path.exists()
            else fetch(commit_url, 5 * 1024 * 1024)
        )
        (directory / "fix-commit-evaluator.json").write_bytes(metadata)
        commit = json.loads(metadata)
        row["pre_commit"] = commit["parents"][0]["sha"]
        row["changed_files_evaluator"] = [
            f["filename"] for f in commit.get("files", [])
        ]
        row["pre_definition"] = (
            "first parent of supplied fix; root cause/oracle pending"
        )
    row["snapshots"] = {}
    for variant in ("pre", "post"):
        url = f"https://codeload.github.com/{repository}/tar.gz/{row[variant + '_commit']}"
        archive_path = directory / f"{variant}.tar.gz"
        content = archive_path.read_bytes() if archive_path.exists() else fetch(url)
        archive_path.write_bytes(content)
        result = unpack(content, directory / variant)
        suffixes = (
            (".py",) if row["language"] == "python" else (".js", ".jsx", ".ts", ".tsx")
        )
        source_files = [
            p
            for p in (directory / variant).rglob("*")
            if p.is_file() and p.suffix in suffixes
        ]
        licenses = [
            p.relative_to(directory / variant).as_posix()
            for p in (directory / variant).glob("*")
            if p.is_file() and p.name.upper().startswith(("LICENSE", "COPYING"))
        ]
        row["snapshots"][variant] = {
            **result,
            "url": url,
            "archive_sha256": hashlib.sha256(content).hexdigest(),
            "source_files": len(source_files),
            "license_files": licenses,
            "license_review": "pending",
        }
    row["collection_status"] = "downloaded"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--collect", type=int, default=20)
    parser.add_argument("--resume", type=Path)
    args = parser.parse_args()
    if args.resume:
        path = args.resume
        output = path.parent
        manifest = json.loads(path.read_text())
        rows = manifest["records"]
        manifest["collector_errata"] = (
            "Initial parser rejected the archive top-level directory. Fixed directory handling; replay saved archives with unchanged selection and source revisions. Advisory IDs sorted lexically, not chronologically."
        )
    else:
        output = MATERIALS / f"phase-two-real-pairs-{uuid4()}"
        output.mkdir()
        rows = choose()
        manifest = {
            "schema_version": 1,
            "scope": "20 full pre/post pilot pairs; independent truth not yet validated",
            "selection": "descending advisory ID per language, one per repository; frozen before any scan; no replacement of download failures",
            "inputs": {
                name: hashlib.sha256((MATERIALS / name).read_bytes()).hexdigest()
                for name in ("vul4py.csv", "ossf-benchmark.tar.gz")
            },
            "records": rows,
        }
        path = output / "manifest.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    print("MANIFEST=" + str(path), flush=True)
    for row in rows[: args.collect]:
        if row.get("collection_status") == "downloaded":
            continue
        if row.get("collection_error"):
            row.setdefault("collection_attempts", []).append(
                row.pop("collection_error")
            )
        try:
            collect(output, row)
        except Exception as exc:  # noqa: BLE001 - preserve each collection failure
            row["collection_status"] = "failed"
            row["collection_error"] = {"type": type(exc).__name__, "message": str(exc)}
        path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
        print(row["cve"], row["language"], row["collection_status"], flush=True)
    print("MANIFEST=" + str(path), flush=True)


if __name__ == "__main__":
    main()
