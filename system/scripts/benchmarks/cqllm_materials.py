"""Freeze every author CSV row; keep reference QL and evaluator out of prompts."""

import csv
import hashlib
import io
import json
import tarfile
from pathlib import Path

from scripts.benchmarks.mechanical_pipeline import save

REPO = Path(__file__).resolve().parents[3]
COMMIT = "9e2abe086b7b2cc55fa22c0fc9305e972b16157f"
RELEASE_SHA = "def95636cf18f9f8ddbd566edadb5a6d1bc05167cbda7cd67c59fe5c88d1c8b7"
RELEASE_URL = "https://github.com/Arashiailing/CQLLM/releases/download/v1.0/CQLLM.zip"


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def freeze(root):
    archive = REPO / "benchmarks/datasets/raw/rules/cqllm-slice-9e2abe0.tar.gz"
    with tarfile.open(archive) as bundle:
        member = next(
            x for x in bundle.getmembers() if x.name.endswith("/最终版prompt.csv")
        )
        raw = bundle.extractfile(member).read()
    rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
    if len(rows) != 298 or set(rows[0]) != {
        "CWE-id",
        "Query_id",
        "Name",
        "Vul-type",
        "Description",
    }:
        raise RuntimeError("Author requirement table identity changed")
    manifest = {
        "source_commit": COMMIT,
        "source_archive_sha256": sha(archive),
        "requirements_sha256": hashlib.sha256(raw).hexdigest(),
        "rows": 298,
        "unique_query_ids": len({r["Query_id"] for r in rows}),
        "unique_cwes": len({r["CWE-id"] for r in rows}),
        "arms": ["no_rag", "current_rag"],
        "planned_tasks": 596,
        "tasks": [
            {"id": f"row-{i:04}", "requirement": row} for i, row in enumerate(rows, 1)
        ],
        "scope": "CQLLM metadata-to-query component benchmark using platform provider, retrieval and CodeQL adapters; not source-bound Rule8 workflow or LoRA replication",
        "semantic_correctness": "not_evaluated_without_independent_location_and_negative_gold",
        "author_test_database_release": {"url": RELEASE_URL, "sha256": RELEASE_SHA},
    }
    path = root / "manifest.json"
    if path.exists() and json.loads(path.read_text()) != manifest:
        raise RuntimeError("Frozen CQLLM manifest changed")
    save(path, manifest)
    return manifest
