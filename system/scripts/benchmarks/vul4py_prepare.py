"""Freeze all official Vul4Py cases with shallow Git snapshots and explicit failures."""

import argparse
import csv
import hashlib
import importlib.util
import io
import json
import shutil
import subprocess
import tarfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REVISION = "2649d7b89e796738ebc2bc3fa9480dff5ae15898"


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def command(args, log, timeout=240):
    result = subprocess.run(args, capture_output=True, timeout=timeout, check=False)
    with log.open("ab") as stream:
        stream.write(("$ " + " ".join(map(str, args)) + "\n").encode())
        stream.write(result.stderr)
    if result.returncode:
        raise RuntimeError(
            f"{args[0]} failed ({result.returncode}); see acquisition log"
        )
    return result.stdout


def extract(repository, ref, destination, log):
    if destination.exists():
        raise RuntimeError("Unreceipted source exists; inspect before retry")
    data = command(["git", "-C", str(repository), "archive", ref], log)
    destination.mkdir()
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        archive.extractall(destination, filter="data")
    return hashlib.sha256(data).hexdigest()


def prepare_case(row, output, upstream):
    started = time.perf_counter()
    identity = row["vuln_id"]
    receipt = output / "acquisition" / f"{identity}.json"
    if receipt.exists():
        return json.loads(receipt.read_text())
    case = output / "workspaces" / identity
    case.mkdir(parents=True, exist_ok=True)
    log = case / "acquisition.log"
    result = {**row, "upstream_commit": REVISION, "status": "preparing"}
    save(output / "acquisition" / f"{identity}.started.json", result)
    try:
        if shutil.disk_usage(output).free < 12 * 1024**3:
            raise RuntimeError("Insufficient free space for further full snapshots")
        repository = case / "evaluator-git"
        if not repository.exists():
            command(["git", "init", "--bare", str(repository)], log)
        fix = row["fix_commit"]
        command(
            ["git", "-C", str(repository), "fetch", "--depth=2", row["repo_url"], fix],
            log,
        )
        parent = (
            command(["git", "-C", str(repository), "rev-parse", f"{fix}^"], log)
            .decode()
            .strip()
        )
        source_hashes = {
            name: extract(repository, ref, case / name, log)
            for name, ref in (("fixed", fix), ("vulnerable", parent))
        }
        helper = load_module(upstream / "scripts/prepare.py", "official_prepare")
        changed = (
            command(
                ["git", "-C", str(repository), "diff", "--name-status", parent, fix],
                log,
            )
            .decode()
            .splitlines()
        )
        tests, code = [], []
        for entry in changed:
            parts = entry.split("\t")
            path = parts[-1]
            if parts[0][0] in {"A", "M"} and path.endswith(".py"):
                (tests if helper.is_test_path(path) else code).append(path)
        helper.write_meta(
            case,
            identity,
            row["repo_url"],
            fix,
            parent,
            helper.collect_baseline_tests(case / "vulnerable"),
            tests,
            code,
        )
        meta = json.loads((case / "meta.json").read_text())
        override = upstream / "dataset/meta_overrides" / f"{identity}.json"
        if override.exists():
            apply = load_module(
                upstream / "scripts/apply_overrides.py", "official_overrides"
            )
            meta = apply.apply(meta, json.loads(override.read_text()))
            save(case / "meta.json", meta)
        result.update(
            status="prepared",
            vulnerable_ref=parent,
            archive_sha256=source_hashes,
            official_override=override.exists(),
            baseline_files=len(meta["baseline_test_files"]),
            exploit_files=len(meta["new_test_files"]),
            model_source=str(case / "vulnerable"),
            evaluator_only_fixed=str(case / "fixed"),
        )
    except (
        OSError,
        RuntimeError,
        subprocess.TimeoutExpired,
        tarfile.TarError,
    ) as error:
        result.update(status="preparation_failed", error=str(error))
    result["seconds"] = time.perf_counter() - started
    save(receipt, result)
    print(identity, result["status"], flush=True)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--jobs", type=int, default=2)
    args = parser.parse_args()
    output = args.output.resolve()
    upstream = output / "upstream"
    dataset = upstream / "dataset/vul4py.csv"
    rows = list(csv.DictReader(dataset.open(newline="")))
    ids = (upstream / "dataset/ok.txt").read_text().split()
    if (
        len(rows) != 100
        or len(set(ids)) != 100
        or {r["vuln_id"] for r in rows} != set(ids)
    ):
        raise RuntimeError("Official 100-case identity mismatch")
    save(
        output / "manifest.json",
        {
            "upstream_commit": REVISION,
            "cases": rows,
            "count": 100,
            "csv_sha256": hashlib.sha256(dataset.read_bytes()).hexdigest(),
            "case_identity": "official ok.txt full 100; no sampling",
            "source_access": "vulnerable only for model; Git and fixed evaluator-only",
        },
    )
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        results = list(pool.map(lambda row: prepare_case(row, output, upstream), rows))
    save(output / "preparation-summary.json", {"cases": results, "total": len(results)})


if __name__ == "__main__":
    main()
