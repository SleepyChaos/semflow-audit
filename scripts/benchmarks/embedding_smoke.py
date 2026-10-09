"""Probe real embeddings and optionally index existing shared technical documents.

Reads credentials from settings. Reports counts and timings, never keys or vectors.
This checks integration only; it does not measure rule-generation quality.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path
from time import monotonic
from uuid import UUID, uuid4

from app.adapters.ai.provider import CompatibleModel
from app.adapters.retrieval.knowledge import KnowledgeRetriever, index_document
from app.core.audit_config import audit_settings
from app.core.db import engine
from app.persistence.knowledge_models import KnowledgeChunk
from sqlmodel import Session, select


def probe() -> dict:
    texts = [
        "CodeQL taint tracking models sources, sinks and sanitizers.",
        "A parameterized SQL query separates data from executable SQL syntax.",
    ]
    started = monotonic()
    result = CompatibleModel().client.embeddings.create(
        model=audit_settings.EMBEDDING_MODEL,
        input=texts,
        encoding_format="float",
    )
    ordered = sorted(result.data, key=lambda row: row.index)
    assert [row.index for row in ordered] == list(range(len(texts)))
    vectors = [row.embedding for row in ordered]
    assert all(v and all(math.isfinite(x) for x in v) and any(v) for v in vectors)
    assert len({len(v) for v in vectors}) == 1
    assert vectors[0] != vectors[1]
    return {
        "requested_model": audit_settings.EMBEDDING_MODEL,
        "resolved_model": result.model,
        "count": len(vectors),
        "dimensions": len(vectors[0]),
        "elapsed_seconds": round(monotonic() - started, 3),
        "batch_order_and_finite_values": True,
    }


def index_shared() -> list[dict]:
    with Session(engine) as session:
        rows = session.exec(
            select(KnowledgeChunk).where(KnowledgeChunk.owner_id.is_(None))
        ).all()
        # Reconstruct from installed public CodeQL packs before any network call.
        grouped = {}
        for row in rows:
            grouped.setdefault(row.document_id, []).append(row)
        documents = {
            document_id
            for document_id, chunks in grouped.items()
            if all(verified_public_query(row) for row in chunks)
            and any(
                row.embedding is None
                or row.embedding_model != audit_settings.EMBEDDING_MODEL
                for row in chunks
            )
        }
    results = []
    for document_id in sorted(documents, key=str):
        started = monotonic()
        index_document(document_id, None)
        results.append(
            {
                "document_id": str(document_id),
                "status": "indexed",
                "elapsed_seconds": round(monotonic() - started, 3),
            }
        )
    return results


def verified_public_query(row: KnowledgeChunk) -> bool:
    if not row.source.startswith("codeql-pack:"):
        return False
    metadata = row.provenance
    specification = metadata.get("query_pack", "")
    if specification not in {
        audit_settings.PYTHON_QUERY_PACK,
        audit_settings.JAVASCRIPT_QUERY_PACK,
    }:
        return False
    prefix = f"codeql-pack:{specification}/"
    if not row.source.startswith(prefix):
        return False
    name, version = specification.split("@")
    root = (audit_settings.CODEQL_PACK_PATH / name / version).resolve()
    path = (root / row.source[len(prefix) :]).resolve()
    if not path.is_relative_to(root) or not path.is_file() or path.suffix != ".ql":
        return False
    query = path.read_text()
    if hashlib.sha256(query.encode()).hexdigest() != metadata.get("source_sha256"):
        return False
    expected = (
        f"# {row.title} ({row.language}, {path.parent.name})\n"
        f"Fixed query pack: {specification}; language API: {metadata.get('api_version')}. "
        "This official query illustrates its own semantics. It does not establish new "
        "framework coverage or independent validation of a generated query. Imports "
        "and PathGraph types must match the fixed library version.\n"
        f"```ql\n{query}\n```\n"
    )
    return row.content == expected and metadata.get("license") == "MIT"


def search_smoke() -> list[dict]:
    results = []
    for language, version, query in [
        ("python", "4.0.10", "Untrusted input reaches eval dynamic code execution"),
        ("javascript", "2.4.0", "User input flows into database SQL query"),
    ]:
        for mode in ("vector", "hybrid"):
            started = monotonic()
            hits = KnowledgeRetriever().retrieve(
                uuid4(), language, query, top_k=3, api_version=version, mode=mode
            )
            assert hits
            assert all("pgvector_cosine_rrf" in hit["methods"] for hit in hits)
            assert all(hit["provenance"].get("api_version") == version for hit in hits)
            with Session(engine) as session:
                for hit in hits:
                    row = session.get(KnowledgeChunk, UUID(hit["id"]))
                    assert row is not None and row.owner_id is None
            results.append(
                {
                    "language": language,
                    "mode": mode,
                    "api_version": version,
                    "elapsed_seconds": round(monotonic() - started, 3),
                    "sources": [hit["source"] for hit in hits],
                    "version_and_shared_scope_verified": True,
                }
            )
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index-shared", action="store_true")
    parser.add_argument("--search", action="store_true")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/research/embedding-smoke.json"),
    )
    args = parser.parse_args()
    report = {"kind": "integration_smoke_not_quality_benchmark", "probe": probe()}
    if args.index_shared:
        report["indexed_documents"] = index_shared()
    if args.search:
        report["search"] = search_smoke()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
