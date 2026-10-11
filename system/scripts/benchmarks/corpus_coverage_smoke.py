"""Measure fixed-corpus retrieval coverage, not generated-rule effectiveness."""

import argparse
import json
import time
from collections import Counter
from pathlib import Path
from uuid import UUID, uuid4

from app.adapters.ai.provider import CompatibleModel
from app.adapters.codeql.custom import fixed_dependencies
from app.adapters.retrieval.dual_corpus import complete_document
from app.adapters.retrieval.knowledge import KnowledgeRetriever
from app.domain.audit import AuditError
from app.services.context_materials import save_json

ROOT = Path(__file__).resolve().parents[3]
CASES = [
    ("CWE-094", "Code injection eval"),
    ("CWE-089", "SQL injection database query"),
    ("CWE-079", "Reflected XSS cross-site scripting"),
    ("CWE-078", "Command injection shell execution"),
    ("CWE-022", "Path traversal file access"),
    ("CWE-918", "Server-side request forgery"),
    ("CWE-502", "Unsafe deserialization"),
    ("CWE-611", "XML external entity injection"),
    ("CWE-943", "NoSQL injection query"),
    ("CWE-730", "Regular expression injection ReDoS"),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", choices=["v3", "v4"], default="v3")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = (
        args.output or ROOT / f"artifacts/research/corpus-coverage-{args.revision}.json"
    )
    if output.exists():
        raise RuntimeError("Preserve completed coverage records; choose a new output")
    manifest = json.loads(
        (
            ROOT / f"artifacts/materials/rag-corpus-{args.revision}/manifest.json"
        ).read_text()
    )
    identifiers = [
        UUID(r["document_id"])
        for r in [*manifest["reference"], *manifest["rule_example"]]
    ]
    owner = uuid4()  # Public-only read; no persisted account or private material.
    records = []
    for language in ["python", "javascript"]:
        version = fixed_dependencies(language)[f"codeql/{language}-all"]["version"]
        for cwe, description in CASES:
            query = f"{language} {cwe} {description} API source sink sanitizer"
            vector = CompatibleModel().embed([query])[0]
            for mode in ["bm25", "hybrid"]:
                start = time.perf_counter()
                record = {
                    "language": language,
                    "cwe": cwe,
                    "query": query,
                    "mode": mode,
                    "slots": {},
                    "status": "passed",
                }
                try:
                    for corpus in ["reference", "rule_example"]:
                        found = KnowledgeRetriever().retrieve(
                            owner,
                            language,
                            query,
                            top_k=2,
                            api_version=version,
                            mode=mode,
                            corpus=corpus,
                            query_vector=vector,
                            example_cwe=cwe if corpus == "rule_example" else None,
                            document_ids=identifiers,
                            active_only=args.revision == "v4",
                        )
                        if corpus == "rule_example":
                            found = [complete_document(owner, r) for r in found]
                        record["slots"][corpus] = [
                            {
                                "title": r["title"],
                                "document_id": r["document_id"],
                                "content_chars": len(r["content"]),
                                "validation": r["provenance"].get("validation"),
                                "methods": r.get("methods"),
                            }
                            for r in found
                        ]
                        if not found:
                            record["status"] = "materials_missing"
                except AuditError as exc:
                    record["status"] = "error"
                    record["error"] = {"code": exc.code, "message": str(exc)}
                record["retrieval_seconds_excluding_shared_query_embedding"] = (
                    time.perf_counter() - start
                )
                records.append(record)
                save_json(
                    output,
                    {"records": records},
                )
    report = {
        "revision": args.revision,
        "active_only": args.revision == "v4",
        "meaning": "40 retrieval checks over 20 language/CWE tasks. No rule generation, compiler execution or vulnerability accuracy is inferred. Matching CWE tags and nonempty slots establish availability, not relevance correctness.",
        "checks": len(records),
        "statuses": dict(Counter(r["status"] for r in records)),
        "by_mode": {
            mode: dict(Counter(r["status"] for r in records if r["mode"] == mode))
            for mode in ["bm25", "hybrid"]
        },
        "records": records,
    }
    save_json(output, report)
    print(
        json.dumps(
            {k: v for k, v in report.items() if k != "records"}, ensure_ascii=False
        )
    )


if __name__ == "__main__":
    main()
