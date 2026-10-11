"""Fixed-corpus retrieval diagnostics; metadata fit is not human relevance gold."""

import json
import time
from uuid import UUID, uuid4

from app.adapters.ai.provider import CompatibleModel
from app.adapters.codeql.custom import fixed_dependencies
from app.adapters.retrieval.knowledge import KnowledgeRetriever

from scripts.benchmarks.corpus_coverage_smoke import CASES
from scripts.benchmarks.formal_freeze import OUTPUT, save


def main():
    config = json.loads((OUTPUT / "config.json").read_text())
    documents = [UUID(s) for s in config["corpus_document_ids"]]
    rows, embedding_calls = [], 0
    owner = uuid4()
    directory = OUTPUT / "retrieval"
    for language in ("python", "javascript"):
        version = fixed_dependencies(language)[f"codeql/{language}-all"]["version"]
        for cwe, description in CASES:
            query = f"{language} {cwe} {description} source sink sanitizer API"
            query_path = directory / f"{language}-{cwe}.json"
            if query_path.exists():
                rows.extend(json.loads(query_path.read_text())["records"])
                continue
            start = time.perf_counter()
            vector, embedding_error = None, None
            try:
                vector = CompatibleModel().embed([query])[0]
                embedding_calls += 1
            except Exception as exc:  # noqa: BLE001 - persist failure at benchmark boundary
                embedding_error = {
                    "type": type(exc).__name__,
                    "message": str(exc)[:500],
                }
            embedding_seconds = time.perf_counter() - start
            group = []
            for mode in ("bm25", "vector", "hybrid"):
                began = time.perf_counter()
                row = {
                    "language": language,
                    "cwe": cwe,
                    "query": query,
                    "mode": mode,
                    "slots": {},
                    "embedding_seconds": embedding_seconds if mode != "bm25" else 0,
                    "scoring": "availability_and_metadata_fit_only_no_human_qrels",
                }
                try:
                    if mode != "bm25" and vector is None:
                        raise RuntimeError(
                            "Embedding unavailable; no silent lexical fallback"
                        )
                    for corpus, k in (("reference", 3), ("rule_example", 2)):
                        records = KnowledgeRetriever().retrieve(
                            owner,
                            language,
                            query,
                            top_k=k,
                            api_version=version,
                            mode=mode,
                            corpus=corpus,
                            query_vector=vector,
                            document_ids=documents,
                            active_only=True,
                        )
                        row["slots"][corpus] = [
                            {
                                key: r.get(key)
                                for key in (
                                    "id",
                                    "title",
                                    "source",
                                    "corpus",
                                    "score",
                                    "provenance",
                                )
                            }
                            for r in records
                        ]
                    examples = row["slots"]["rule_example"]
                    row["metadata_CWE_example_hits"] = sum(
                        cwe
                        in r["provenance"].get("cwe_ids", [r["provenance"].get("cwe")])
                        for r in examples
                    )
                    row["status"] = "succeeded"
                except Exception as exc:  # noqa: BLE001 - persist failure at benchmark boundary
                    row.update(
                        status="failed",
                        error={"type": type(exc).__name__, "message": str(exc)[:500]},
                    )
                row["retrieval_seconds"] = time.perf_counter() - began
                group.append(row)
            save(
                query_path,
                {
                    "records": group,
                    "embedding_error": embedding_error,
                    "embedding_calls": 1,
                    "query_vector_dimension": len(vector) if vector else None,
                },
            )
            rows.extend(group)
            print(
                json.dumps(
                    {
                        "language": language,
                        "cwe": cwe,
                        "statuses": [r["status"] for r in group],
                    }
                ),
                flush=True,
            )
    save(
        directory / "summary.json",
        {
            "records": rows,
            "queries": 20,
            "configurations": 60,
            "new_successful_embedding_calls_this_invocation": embedding_calls,
            "human_relevance_metrics": "not_evaluated_no_independent_qrels",
            "scope": "generic retrieval; generation role routing may force BM25 for API slots",
        },
    )


if __name__ == "__main__":
    main()
