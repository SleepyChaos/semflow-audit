"""Exercise actual dual-corpus product slots, distinct from generic availability."""

import argparse
import json
from pathlib import Path
from uuid import uuid4

from app.adapters.codeql.custom import fixed_dependencies
from app.adapters.retrieval.dual_corpus import retrieve_both
from app.domain.audit import AuditError
from app.services.context_materials import save_json

from scripts.benchmarks.corpus_coverage_smoke import CASES, ROOT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cwe")
    args = parser.parse_args()
    if args.output.exists():
        raise RuntimeError("Keep prior product retrieval results")
    corpus = json.loads(
        (ROOT / "artifacts/materials/rag-corpus-v4/manifest.json").read_text()
    )
    ids = [
        r["document_id"] for role in ("reference", "rule_example") for r in corpus[role]
    ]
    rows = []
    for language in ("python", "javascript"):
        version = fixed_dependencies(language)[f"codeql/{language}-all"]["version"]
        for cwe, description in CASES:
            if args.cwe and args.cwe != cwe:
                continue
            row = {"language": language, "cwe": cwe, "status": "passed"}
            try:
                records = retrieve_both(
                    uuid4(),
                    language,
                    f"{cwe} {description}",
                    version,
                    mode="bm25",
                    document_ids=ids,
                    enhanced=True,
                    exact_cwe=True,
                )
                row["records"] = [
                    {
                        "id": r["id"],
                        "title": r["title"],
                        "corpus": r["corpus"],
                        "retrieval_slot": r["retrieval_slot"],
                        "cwe_ids": r["provenance"].get("cwe_ids"),
                    }
                    for r in records
                ]
            except AuditError as exc:
                row["status"] = "failed"
                row["error"] = {"code": exc.code, "message": str(exc)}
            rows.append(row)
            save_json(
                args.output,
                {
                    "records": rows,
                    "meaning": "Product-role material availability, not detector accuracy",
                },
            )
            print(json.dumps(row, ensure_ascii=False), flush=True)
    save_json(
        args.output,
        {
            "checks": len(rows),
            "passed": sum(r["status"] == "passed" for r in rows),
            "records": rows,
            "meaning": "Product-role material availability, not detector accuracy",
        },
    )


if __name__ == "__main__":
    main()
