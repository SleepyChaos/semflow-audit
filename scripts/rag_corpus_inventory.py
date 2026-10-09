"""Count documents, versions and current vector coverage without exporting content."""

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from app.adapters.retrieval.embedding_identity import embedding_identity
from app.core.db import engine
from app.persistence.knowledge_models import KnowledgeChunk as K
from sqlmodel import Session, select


def inventory():
    with Session(engine) as session:
        rows = session.exec(
            select(
                K.document_id,
                K.source,
                K.language,
                K.corpus,
                K.provenance,
                K.embedding_identity,
                K.embedding.is_not(None),
                K.owner_id.is_(None),
            )
        ).all()
    documents = defaultdict(list)
    for row in rows:
        documents[str(row[0])].append(row)
    public = [v for v in documents.values() if v[0][-1]]
    identity = embedding_identity()
    by_corpus = {}
    for corpus in ["reference", "rule_example", "unclassified"]:
        chosen = [v for v in public if v[0][3] == corpus]
        states = Counter()
        eligible, indexed = [], []
        for parts in chosen:
            validation = parts[0][4].get("validation")
            state = (
                validation.get("status", "unspecified")
                if isinstance(validation, dict)
                else "reference_source"
            )
            states[state] += 1
            if corpus != "rule_example" or state != "failed":
                eligible.append(parts)
                if all(r[5] == identity and r[6] for r in parts):
                    indexed.append(parts)
        by_corpus[corpus] = {
            "document_versions": len(chosen),
            "unique_sources": len({v[0][1] for v in chosen}),
            "chunks": sum(len(v) for v in chosen),
            "validation": dict(states),
            "eligible_document_versions_under_current_filter": len(eligible),
            "eligible_unique_sources": len({v[0][1] for v in eligible}),
            "eligible_fully_current_indexed_document_versions": len(indexed),
            "eligible_fully_current_indexed_unique_sources": len(
                {v[0][1] for v in indexed}
            ),
        }
    return {
        "total_document_versions": len(documents),
        "total_chunks": len(rows),
        "public_document_versions": len(public),
        "public_chunks": sum(len(v) for v in public),
        "private_document_versions": len(documents) - len(public),
        "public_by_corpus": by_corpus,
        "public_by_language": dict(Counter(v[0][2] for v in public)),
        "public_current_indexed_chunks": sum(
            r[-1] and r[5] == identity and r[6] for r in rows
        ),
        "public_chunks_by_language_corpus": dict(
            Counter(f"{r[2]}:{r[3]}" for r in rows if r[-1])
        ),
        "note": "Historical versions count separately; distinct sources can still refer to the same official query. Legacy unverified examples are allowed by the current filter and are not claimed development-validated.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = inventory()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
