"""Pinned official development oracles; upgrade versions without rewriting history."""

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from uuid import UUID

import codeql_corpus_sources as sources
import curate_rule_corpus as curator
import httpx
from app.adapters.retrieval.knowledge import import_knowledge, index_document
from app.core.audit_config import audit_settings
from app.services.context_materials import save_json
from corpus_expansion_sources import local_modules

ROOT = sources.ROOT
OUTPUT = ROOT / "artifacts/materials/rag-corpus-v4"


def collect():
    sources.OUTPUT = curator.OUTPUT = OUTPUT
    manifest = OUTPUT / "development-manifest.json"
    if manifest.exists():
        return json.loads(manifest.read_text())
    rows = []
    with httpx.Client(
        timeout=40, transport=httpx.HTTPTransport(retries=2), trust_env=False
    ) as client:
        for language in ("javascript", "python"):
            for row in curator.collect_examples(
                language,
                client,
                180,
                on_example=lambda r, language=language: print(
                    "DOWNLOADED=" + language + "/" + Path(r["query_path"]).name,
                    flush=True,
                ),
            ):
                query = Path(row["query_path"])
                spec = getattr(audit_settings, language.upper() + "_QUERY_PACK")
                name, version = spec.split("@")
                root = audit_settings.CODEQL_PACK_PATH / name / version
                tree = {e["path"]: e for e in sources.source_tree(language)["tree"]}
                modules = local_modules(query, root, tree)
                test_directory = ROOT / row["metadata"]["bundle"] / "tests"
                parent = query.parent.relative_to(root).as_posix() + "/"
                for path, body in modules.items():
                    target = test_directory / (path.removeprefix(parent))
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(body)
                # Retain inherited official extractor options (not the expected labels).
                ref = next(
                    e
                    for e in row["metadata"]["official_development_tests"]
                    if e["url"].endswith(query.stem + ".qlref")
                )
                relative = ref["url"].split(f"/{language}/", 1)[1]
                options = []
                for ancestor in reversed(Path(relative).parents):
                    entry = tree.get((ancestor / "options").as_posix())
                    if entry:
                        destination = (
                            OUTPUT / "inherited-options" / language / entry["path"]
                        )
                        sources.download(client, language, entry, destination)
                        options.append(destination.read_text())
                if options:
                    (test_directory / "options").write_text("\n".join(options))
                row["metadata"]["cwe_ids"] = sorted(
                    {
                        "CWE-" + x.zfill(3)
                        for x in re.findall(
                            r"external/cwe/cwe-(\d+)", query.read_text(), re.IGNORECASE
                        )
                    }
                )
                row["metadata"]["harness"] = {
                    "version": "official-options-and-local-helpers-v4",
                    "inherited_options": options,
                    "modules": {k: sources.sha(v) for k, v in modules.items()},
                }
                rows.append(row)
                print("COLLECTED=" + language + "/" + query.name, flush=True)
    save_json(manifest, rows)
    return rows


def validate(row):
    unit = ROOT / row["metadata"]["bundle"]
    receipt = unit / "development-receipt.json"
    from app.services.context_materials import digest
    from corpus_validation_identity import verify_official_inputs

    identity, changed_at = verify_official_inputs(row)
    binding = unit / "development-input-receipt.json"
    if binding.exists():
        saved = json.loads(binding.read_text())
        if saved["input_digest"] != identity or saved["log_digest"] != digest(
            (unit / "test-execution.log").read_text()
        ):
            raise ValueError("Official test inputs/log changed after validation")
    if receipt.exists() and changed_at <= receipt.stat().st_mtime:
        row["metadata"]["validation"] = json.loads(receipt.read_text())
    else:
        # Retain earlier observations; changed extractor files require a fresh run.
        if receipt.exists():
            save_json(
                unit / "prior-development-receipt.json", json.loads(receipt.read_text())
            )
        row["metadata"]["validation"] = curator.validate_example(row)
        save_json(receipt, row["metadata"]["validation"])
    save_json(
        binding,
        {
            "input_digest": identity,
            "log_digest": digest((unit / "test-execution.log").read_text()),
            "validation": row["metadata"]["validation"],
            "meaning": "Complete current inputs and unchanged official blobs verified; old receipts bound after source checks, dirty inputs rerun.",
        },
    )
    row["metadata"]["harness"]["input_digest"] = identity
    return row


def index_once(document_id):
    from app.adapters.retrieval.embedding_identity import embedding_identity
    from app.core.db import engine
    from app.persistence.knowledge_models import KnowledgeChunk
    from sqlmodel import Session, select

    with Session(engine) as db:
        rows = db.exec(
            select(KnowledgeChunk).where(KnowledgeChunk.document_id == document_id)
        ).all()
        ready = rows and all(
            r.embedding is not None and r.embedding_identity == embedding_identity()
            for r in rows
        )
    if not ready:
        index_document(document_id, None)


def main():
    rows = collect()
    # Different test directories and fixed read-only packs; no shared test DB writes.
    validated = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(validate, r) for r in rows]
        for future in as_completed(futures):
            row = future.result()
            validated.append(row)
            save_json(OUTPUT / "validated.json", validated)
            print(
                json.dumps(
                    {
                        "language": row["language"],
                        "title": row["title"],
                        "validation": row["metadata"]["validation"],
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )
    previous = json.loads(
        (ROOT / "artifacts/materials/rag-corpus-v3/manifest.json").read_text()
    )
    by_query = {(r["language"], Path(r["query_path"]).name): r for r in validated}
    active = {
        "reference": previous["reference"],
        "rule_example": [],
        "development": validated,
    }
    from app.adapters.retrieval.dual_corpus import complete_document

    for original in previous["rule_example"]:
        language = original["language"]
        key = (language, Path(original["query_path"]).name)
        row = by_query.get(key)
        metadata = dict(original["metadata"])
        raw = Path(original["query_path"]).read_text()
        metadata["cwe_ids"] = sorted(
            {
                "CWE-" + n.zfill(3)
                for n in re.findall(r"external/cwe/cwe-(\d+)", raw, re.IGNORECASE)
            }
        )
        if row:
            metadata.update(
                {
                    k: row["metadata"][k]
                    for k in ("validation", "official_development_tests", "harness")
                }
            )
        # Keep historical compiler receipts, but a fresh failed official test excludes
        # the current version; compiler success must not override that failure.
        if row:
            metadata["official_development_result"] = row["metadata"]["validation"]
        record = complete_document(
            None,
            {"document_id": original["document_id"], "version": original["version"]},
        )
        status = metadata["validation"]["status"]
        kind = metadata["validation"].get("kind", "not_run")
        content = re.sub(
            r"Developer validation: (?:failed|passed|not_run)\.",
            f"Validation tier: {kind}, status: {status}.",
            record["content"],
        )
        # Update descriptive validation labels only, never QL bodies or oracle labels.
        assert re.findall(r"```ql\n(.*?)\n```", content, re.DOTALL) == re.findall(
            r"```ql\n(.*?)\n```", record["content"], re.DOTALL
        )
        imported = import_knowledge(
            None,
            original["title"],
            f"curated-codeql-example:{language}/{key[1]}",
            language,
            content,
            metadata,
            corpus="rule_example",
        )
        active["rule_example"].append({**original, **imported, "metadata": metadata})
        if metadata.get("validation", {}).get("status") == "passed":
            index_once(UUID(imported["document_id"]))
        save_json(OUTPUT / "manifest.json", active)
    active["summary"] = {
        "reference_sources": len(active["reference"]),
        "examples": len(active["rule_example"]),
        "official_examples_passed": sum(
            r["metadata"]["validation"].get("kind") == "official_development_test"
            and r["metadata"]["validation"]["status"] == "passed"
            for r in active["rule_example"]
        ),
        "official_tests_passed": sum(
            r["metadata"]["validation"]["status"] == "passed" for r in validated
        ),
        "official_tests_failed": sum(
            r["metadata"]["validation"]["status"] != "passed" for r in validated
        ),
    }
    save_json(OUTPUT / "manifest.json", active)
    print(json.dumps(active["summary"]), flush=True)


if __name__ == "__main__":
    main()
