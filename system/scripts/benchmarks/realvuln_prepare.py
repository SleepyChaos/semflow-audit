"""Acquire exact paper target commits without executing target applications."""

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PAPER_REVISION = "55350cdc0f0f7db85d1f0b97649df07e6d63c665"


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def command(args, timeout=180):
    result = subprocess.run(
        args, capture_output=True, text=True, timeout=timeout, check=False
    )
    if result.returncode:
        raise RuntimeError(result.stderr[-1500:])
    return result.stdout.strip()


def acquire(slug, target, alternatives, output):
    directory = output / "repositories" / slug
    directory.parent.mkdir(parents=True, exist_ok=True)
    if not directory.exists():
        command(["git", "init", str(directory)])
    attempts = []
    for url in dict.fromkeys([target["repo_url"], *alternatives]):
        try:
            command(
                [
                    "git",
                    "-C",
                    str(directory),
                    "fetch",
                    "--depth=1",
                    url,
                    target["commit_sha"],
                ]
            )
            command(["git", "-C", str(directory), "checkout", "--detach", "FETCH_HEAD"])
            actual = command(["git", "-C", str(directory), "rev-parse", "HEAD"])
            if actual != target["commit_sha"]:
                raise RuntimeError("Fetched commit differs from the paper manifest")
            source = output / "sources" / slug
            if not source.exists():
                shutil.copytree(
                    directory, source, ignore=shutil.ignore_patterns(".git")
                )
            from app.adapters.snapshot import snapshot_digest

            return {
                "id": slug,
                "language": "python",
                "source": str(source),
                "files": sum(p.is_file() for p in source.rglob("*")),
                "input_regime": "pinned full repository excluding .git; no evaluator labels",
                "commit": actual,
                "url": url,
                "snapshot": snapshot_digest(source),
                "status": "ready",
                "attempts": attempts,
            }
        except (RuntimeError, subprocess.TimeoutExpired) as exc:
            attempts.append({"url": url, "error": str(exc)[:1500]})
    return {
        "id": slug,
        "status": "source_unavailable",
        "commit": target["commit_sha"],
        "attempts": attempts,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--reuse-inputs",
        type=Path,
        help="Reuse verified immutable local snapshots without fetching",
    )
    args = parser.parse_args()
    output = args.output.resolve()
    original = ROOT / ".local-workspace/realvuln-paper-original"
    current = ROOT / ".local-workspace/realvuln-upstream"
    manifest = json.loads((original / "benchmark-manifest.json").read_text())
    latest = json.loads((current / "benchmark-manifest.json").read_text())
    gold = output / "evaluator-only"
    gold.mkdir(parents=True, exist_ok=True)
    for name in ("ground-truth", "config", "scan-results"):
        if not (gold / name).exists():
            shutil.copytree(original / name, gold / name)
    # Latest v1 matcher includes the acceptable-location semantics described in PDF.
    scorer_source = ROOT / ".local-workspace/realvuln-v1-original"
    for name in ("scorer", "parsers"):
        if not (gold / name).exists():
            shutil.copytree(
                scorer_source / name,
                gold / name,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )
    frozen = output / "implementation"
    if not frozen.exists():
        shutil.copytree(
            ROOT / "system/backend/app",
            frozen / "system/backend/app",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "frontend"),
        )
        (frozen / ".env").symlink_to(ROOT / ".env")
    hashes = {
        str(p.relative_to(frozen)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in frozen.rglob("*")
        if p.is_file() and p.suffix in {".py", ".txt"}
    }
    save(output / "implementation-hashes.json", hashes)
    save(
        output / "dataset.json",
        {
            "source": "author official GitHub history; Hugging Face unavailable",
            "paper_compatible_revision": PAPER_REVISION,
            "v1_tag_revision": "d98e9fc91273702c9547663b6906d1fc494d4fcc",
            "manifest": manifest,
            "manifest_sha256": hashlib.sha256(
                (original / "benchmark-manifest.json").read_bytes()
            ).hexdigest(),
            "gold_sha256": {
                str(p.relative_to(gold)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in gold.rglob("*")
                if p.is_file()
            },
            "paper_gold_counts": {
                "repositories": 26,
                "vulnerabilities": 676,
                "traps": 120,
            },
            "exact_huggingface_identity_verified": False,
        },
    )
    records = []
    for slug, target in manifest["repos"].items():
        receipt = output / "acquisition" / f"{slug}.json"
        if receipt.exists():
            row = json.loads(receipt.read_text())
        elif args.reuse_inputs:
            from app.adapters.snapshot import snapshot_digest

            previous = args.reuse_inputs.resolve()
            old_dataset = json.loads((previous / "dataset.json").read_text())
            if old_dataset["manifest"] != manifest:
                raise RuntimeError("Reused input manifest differs from the paper")
            row = json.loads((previous / "acquisition" / f"{slug}.json").read_text())
            if row["status"] != "ready" or row["commit"] != target["commit_sha"]:
                raise RuntimeError("Reused source is not the pinned ready commit")
            source = Path(row["source"])
            if snapshot_digest(source) != row["snapshot"]:
                raise RuntimeError("Reused source snapshot changed")
            alias = output / "sources" / slug
            alias.parent.mkdir(parents=True, exist_ok=True)
            alias.symlink_to(source, target_is_directory=True)
            row = {**row, "source": str(alias), "reused_verified_input": str(source)}
            save(receipt, row)
        else:
            alternative = latest["repos"].get(slug, {})
            urls = [alternative["repo_url"]] if alternative.get("repo_url") else []
            row = acquire(slug, target, urls, output)
            save(receipt, row)
        records.append(row)
        save(output / "inputs.json", {"records": records})
        print(
            json.dumps(
                {"id": slug, "status": row["status"], "files": row.get("files")}
            ),
            flush=True,
        )
    save(
        output / "acquisition-summary.json",
        {
            "total": len(records),
            "ready": sum(r["status"] == "ready" for r in records),
            "unavailable": [r["id"] for r in records if r["status"] != "ready"],
        },
    )


if __name__ == "__main__":
    main()
