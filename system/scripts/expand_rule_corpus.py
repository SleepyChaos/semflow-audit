"""Expand pinned official corpus locally, check full bundles, and index eligible additions."""

import argparse
import json
from collections import Counter
from pathlib import Path
from uuid import UUID

from app.adapters.codeql.custom import search_paths
from app.adapters.codeql.process import run_command
from app.adapters.codeql.scanner import CodeQLScanner
from app.adapters.retrieval.embedding_identity import embedding_identity
from app.adapters.retrieval.knowledge import import_knowledge, index_document
from app.core.audit_config import audit_settings
from app.core.db import engine
from app.domain.audit import AuditError
from app.persistence.knowledge_models import KnowledgeChunk
from app.services.context_materials import save_json
from corpus_expansion_sources import (
    COMMITS,
    OUTPUT,
    ROOT,
    examples,
    previous,
    references,
)
from sqlmodel import Session, select


def compile_group(language, rows):
    if not rows:
        return
    pack = OUTPUT / "compile" / language
    log = OUTPUT / "validation" / f"{language}-check.log"
    args = [
        audit_settings.CODEQL_BIN,
        "query",
        "compile",
        "--check-only",
        "--keep-going",
        "--threads=2",
        f"--ram={audit_settings.CODEQL_RAM}",
        f"--additional-packs={search_paths(pack)}",
    ]
    cli = CodeQLScanner().version()
    try:
        run_command(
            args + [r["query_path"] for r in rows], log, audit_settings.SCAN_TIMEOUT
        )
        for row in rows:
            row["metadata"]["validation"] = {
                "status": "passed",
                "kind": "compiler_only",
                "codeql": cli,
                "log": str(log.relative_to(ROOT)),
                "development_status": "not_run",
                "holdout_status": "not_run",
            }
    except AuditError:
        # A group error does not identify every bad query; check individually before accepting.
        for row in rows:
            local_log = (
                OUTPUT
                / "validation"
                / language
                / (Path(row["query_path"]).stem + ".log")
            )
            try:
                run_command(
                    args + [row["query_path"]], local_log, audit_settings.SCAN_TIMEOUT
                )
                status = "passed"
            except AuditError:
                status = "failed"
            row["metadata"]["validation"] = {
                "status": status,
                "kind": "compiler_only",
                "codeql": cli,
                "log": str(local_log.relative_to(ROOT)),
                "development_status": "not_run",
                "holdout_status": "not_run",
            }


def indexed(document_id):
    with Session(engine) as session:
        rows = session.exec(
            select(
                KnowledgeChunk.embedding_identity, KnowledgeChunk.embedding.is_not(None)
            ).where(
                KnowledgeChunk.document_id == UUID(document_id),
                KnowledgeChunk.owner_id.is_(None),
            )
        ).all()
    return bool(rows) and all(
        identity == embedding_identity() and present for identity, present in rows
    )


def import_row(row, corpus):
    result = import_knowledge(
        None,
        row["title"],
        row["source"],
        row["language"],
        row["content"],
        row["metadata"],
        corpus=corpus,
        content_format="source" if corpus == "reference" else "markdown",
    )
    return {k: v for k, v in {**row, **result}.items() if k != "content"}


def example_source(row):
    return (
        row.get("source")
        or f"curated-codeql-example:{row['language']}/{Path(row['query_path']).name}"
    )


def run(index):
    old = previous()
    manifest_path = OUTPUT / "manifest.json"
    # Checkpoint all completed imports; a restart reuses records and indexing identities.
    manifest = (
        json.loads(manifest_path.read_text())
        if manifest_path.exists()
        else {
            "commits": COMMITS,
            "reference": list(old["reference"]),
            "rule_example": list(old["rule_example"]),
            "skipped": [],
            "errors": [],
        }
    )
    old_sources = {
        f"curated-codeql-example:{r['language']}/{Path(r['query_path']).name}"
        for r in old["rule_example"]
    }
    imported = {example_source(r): r for r in manifest["rule_example"]}
    old_reference_sources = {
        f"pinned-codeql-library:{r['metadata']['library_pack']}/{r['metadata']['source_url'].split('/ql/lib/')[1]}"
        for r in manifest["reference"]
    }
    for language in ["python", "javascript"]:
        for row in references(language):
            if row["source"] not in old_reference_sources:
                manifest["reference"].append(import_row(row, "reference"))
                old_reference_sources.add(row["source"])
                save_json(manifest_path, manifest)
        collected, skipped = examples(language)
        pending = [
            r
            for r in collected
            if r["source"] not in old_sources
            and (
                r["source"] not in imported
                or imported[r["source"]]["metadata"].get("modules")
                != r["metadata"]["modules"]
            )
        ]
        manifest["skipped"] = [
            s for s in manifest["skipped"] if s.get("language") != language
        ] + [{"language": language, **s} for s in skipped]
        print(
            json.dumps(
                {
                    "language": language,
                    "new_examples_to_check": len(pending),
                    "references_total": len(manifest["reference"]),
                }
            ),
            flush=True,
        )
        compile_group(language, pending)
        for row in pending:
            record = import_row(row, "rule_example")
            manifest["rule_example"] = [
                r
                for r in manifest["rule_example"]
                if example_source(r) != row["source"]
            ]
            manifest["rule_example"].append(record)
            imported[row["source"]] = record
            save_json(manifest_path, manifest)
    if index:
        for number, row in enumerate(
            [*manifest["reference"], *manifest["rule_example"]], 1
        ):
            validation = row["metadata"].get("validation")
            if isinstance(validation, dict) and validation.get("status") != "passed":
                continue
            if indexed(row["document_id"]):
                continue
            try:
                index_document(UUID(row["document_id"]), None)
                row["index_status"] = "indexed"
            except (AuditError, OSError) as exc:
                row["index_status"] = "failed"
                manifest["errors"].append(
                    {
                        "document_id": row["document_id"],
                        "operation": "index",
                        "error": type(exc).__name__,
                    }
                )
            save_json(manifest_path, manifest)
            print(
                json.dumps(
                    {
                        "index_progress": number,
                        "title": row.get("title", row.get("topic")),
                        "status": row["index_status"],
                    }
                ),
                flush=True,
            )
    manifest["summary"] = {
        "reference_topics": len(manifest["reference"]),
        "complete_examples": len(manifest["rule_example"]),
        "example_validation": dict(
            Counter(
                (
                    r["metadata"]["validation"].get(
                        "kind", "official_development_test"
                    ),
                    r["metadata"]["validation"]["status"],
                )
                for r in manifest["rule_example"]
            )
        ),
    }
    # JSON object keys must remain strings.
    manifest["summary"]["example_validation"] = {
        f"{kind}:{status}": count
        for (kind, status), count in manifest["summary"]["example_validation"].items()
    }
    save_json(manifest_path, manifest)
    print(json.dumps(manifest["summary"], ensure_ascii=False), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", action="store_true")
    arguments = parser.parse_args()
    run(arguments.index)
