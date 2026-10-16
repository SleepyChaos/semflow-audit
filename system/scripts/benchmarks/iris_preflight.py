"""Freeze IRIS inputs and test production language gates; never invent scan scores."""

import argparse
import csv
import hashlib
import json
import subprocess
import tempfile
from collections import Counter
from pathlib import Path
from typing import Literal
from zipfile import ZipFile

from app.adapters.archive import EXTENSIONS, extract_snapshot
from app.domain.audit import AuditError
from pydantic import TypeAdapter, ValidationError


def git_revision(directory: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(directory), "rev-parse", "HEAD"], text=True
    ).strip()


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def language_gate() -> dict:
    """Use the actual archive adapter and the upload route's declared annotation."""
    from typing import get_args, get_type_hints

    from app.api.routes.audits import upload_run

    annotation = get_type_hints(upload_run, include_extras=True)["language"]
    allowed = get_args(get_args(annotation)[0])
    adapter = TypeAdapter(Literal[allowed])
    try:
        adapter.validate_python("java")
        validation = "accepted"
    except ValidationError as exc:
        validation = exc.errors(include_url=False, include_context=False)
    archive_results = []
    with tempfile.TemporaryDirectory(prefix="iris-language-") as temporary:
        root = Path(temporary)
        bundle = root / "java-only.zip"
        with ZipFile(bundle, "w") as archive:
            archive.writestr("src/Probe.java", "class Probe {}\n")
        for language in allowed:
            try:
                extract_snapshot(bundle, root / language, language)
                archive_results.append({"language": language, "status": "accepted"})
            except AuditError as exc:
                archive_results.append(
                    {"language": language, "status": "rejected", "reason": str(exc)}
                )
    return {"upload_languages": allowed, "java_validation": validation,
            "java_extension": EXTENSIONS.get(".java"), "archive_probes": archive_results,
            "probe_kind": "synthetic language gate, not a vulnerability scan"}


def author_results(repository: Path, projects: list[dict]) -> list[dict]:
    keys = {(p["cwe_id"], p["cve_id"], p["github_username"],
             p["github_repository_name"], p["github_tag"]) for p in projects}
    results = []
    for path in sorted((repository / "results").glob("*.csv")):
        rows = read_csv(path)
        matched = [r for r in rows if (r["CWE ID"], r["CVE"], r["Author"],
                   r["Package "], r["Tag"]) in keys]
        detected = sum(float(r["Recall"]) > 0 for r in matched
                       if r["Recall"] not in {"None", "N/A", ""})
        results.append({"method": path.stem, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                        "csv_rows": len(rows), "matched_rows": len(matched),
                        "matched_detected": detected,
                        "matched_subset_detection_rate": detected / len(matched) if matched else None,
                        "full_manifest_detection_rate": None,
                        "csv_detected_numeric_rows": sum(float(r["Recall"]) > 0 for r in rows
                            if r["Recall"] not in {"None", "N/A", ""})})
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("repository", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    repository = args.repository.resolve()
    dataset = repository / "data/cwe-bench-java"
    manifest = dataset / "data/project_info.csv"
    projects = read_csv(manifest)
    report = {
        "status": "blocked_unsupported_language", "iris_revision": git_revision(repository),
        "dataset_revision": git_revision(dataset),
        "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
        "dataset_tasks": len(projects), "cwe_counts": dict(Counter(p["cwe_id"] for p in projects)),
        "language_gate": language_gate(), "author_csv_results": author_results(repository, projects),
        "platform_evaluated_tasks": 0, "platform_detection_rate": None,
        "platform_precision": None, "platform_f1": None, "comparison_allowed": False,
        "task_statuses": [{"project_slug": p["project_slug"], "status": "not_evaluated",
                           "reason": "production platform does not support Java"} for p in projects],
        "target_sources_present": (dataset / "project-sources").exists(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key != "task_statuses"},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
