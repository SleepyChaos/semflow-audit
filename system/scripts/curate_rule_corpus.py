"""Build pinned public API topics and complete official query/test example units.

Originals are retained under artifacts. Official tests are RAG development assets,
never independent evaluation. No project upload or credentials go to GitHub.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import yaml
from app.adapters.codeql.custom import fixed_dependencies
from app.adapters.codeql.process import run_command
from app.adapters.codeql.scanner import CodeQLScanner
from app.adapters.retrieval.knowledge import import_knowledge, index_document
from app.core.audit_config import audit_settings
from app.domain.audit import AuditError
from app.services.context_materials import save_json
from codeql_corpus_sources import (
    COMMITS,
    OUTPUT,
    ROOT,
    download,
    library_topics,
    sha,
    source_tree,
)


def collect_examples(language, client, limit, on_example=None):
    spec = getattr(audit_settings, language.upper() + "_QUERY_PACK")
    name, version = spec.split("@")
    pack = audit_settings.CODEQL_PACK_PATH / name / version
    tree = source_tree(language)
    assert not tree.get("truncated"), "Frozen per-language tree must be complete"
    by_path = {e["path"]: e for e in tree["tree"]}
    references = [
        e
        for e in tree["tree"]
        if e["path"].endswith(".qlref")
        and "/query-tests/" in e["path"]
        and "Security/" in e["path"]
        and "py2" not in e["path"]
    ]
    priorities = [
        "CWE-094",
        "CWE-089",
        "CWE-079",
        "CWE-078",
        "CWE-022",
        "CWE-502",
        "CWE-918",
    ]
    queries = sorted(
        pack.glob("Security/CWE-*/*.ql"),
        key=lambda p: (
            next((i for i, k in enumerate(priorities) if k in str(p)), 99),
            p.name,
        ),
    )
    results = []
    for query in queries:
        text = query.read_text()
        if len(text) > 6500:
            continue
        relative = query.relative_to(pack).as_posix()
        blob = query.read_bytes()
        official = by_path.get("ql/src/" + relative, {})
        if (
            official.get("sha")
            != hashlib.sha1(
                b"blob " + str(len(blob)).encode() + b"\0" + blob
            ).hexdigest()
        ):
            continue
        candidates = [
            e for e in references if Path(e["path"]).name == query.stem + ".qlref"
        ]
        if not candidates:
            continue
        candidates.sort(
            key=lambda e: (
                "local-threat" in e["path"],
                "/typed/" in e["path"],
                e["path"],
            )
        )
        ref = candidates[0]
        test_root = str(Path(ref["path"]).parent) + "/"
        unit = OUTPUT / "examples" / language / query.stem
        unit.mkdir(parents=True, exist_ok=True)
        (unit / "original.ql").write_text(text)
        files = [
            e
            for e in tree["tree"]
            if e["type"] == "blob"
            and e["path"].startswith(test_root)
            and (
                Path(e["path"]).name == "options"
                or Path(e["path"]).suffix
                in {
                    ".py",
                    ".js",
                    ".jsx",
                    ".vue",
                    ".xsjs",
                    ".raml",
                    ".ts",
                    ".html",
                    ".json",
                    ".ql",
                    ".qll",
                    ".qlref",
                    ".expected",
                    ".yml",
                    ".yaml",
                    ".xml",
                    ".txt",
                }
            )
        ]
        test_directory = unit / "tests"
        with ThreadPoolExecutor(max_workers=6) as pool:
            downloaded = list(
                pool.map(
                    lambda e, folder=test_directory, prefix=test_root: download(
                        client,
                        language,
                        e,
                        folder / e["path"][len(prefix) :],
                    ),
                    files,
                )
            )
        expected = test_directory / (query.stem + ".expected")
        if not expected.exists():
            continue
        # Remove references to other tests. Preserve all original test sources/expectations separately.
        for old_ref in test_directory.rglob("*.qlref"):
            old_ref.unlink()
        # The exact query is a local test entry; its expected file keeps the same basename.
        (test_directory / query.name).write_text(text)
        deps = fixed_dependencies(language)
        (unit / "codeql-pack.lock.yml").write_text(
            yaml.safe_dump({"lockVersion": "1.0.0", "dependencies": deps})
        )
        (test_directory / "codeql-pack.lock.yml").write_text(
            (unit / "codeql-pack.lock.yml").read_text()
        )
        (test_directory / "qlpack.yml").write_text(
            yaml.safe_dump(
                {
                    "name": "audit/reference-tests-" + query.stem.lower(),
                    "version": "0.0.1",
                    "extractor": language,
                    "groups": [language, "test"],
                    "tests": ".",
                    "dependencies": {
                        f"codeql/{language}-all": deps[f"codeql/{language}-all"][
                            "version"
                        ],
                        name: version,
                    },
                }
            )
        )
        metadata = {
            "trust": "pinned_codeql_source",
            "license": "MIT",
            "commit": COMMITS[language],
            "source_sha256": sha(text),
            "api_version": deps[f"codeql/{language}-all"]["version"],
            "query_pack": spec,
            "dependencies": deps,
            "cwe": query.parent.name,
            "imports": re.findall(r"^import (.+)$", text, re.MULTILINE),
            "bundle": str(unit.relative_to(ROOT)),
            "official_development_tests": downloaded,
            "validation": {"status": "not_run"},
            "meaning": "Official query reuse with recoverable pinned dependencies; development tests, not holdout",
        }
        results.append(
            {
                "language": language,
                "title": re.search(r"@name (.+)", text)[1],
                "query_path": str(query),
                "metadata": metadata,
            }
        )
        save_json(unit / "manifest.json", metadata)
        if on_example:
            on_example(results[-1])
        if len(results) >= limit:
            break
    return results


def validate_example(row):
    unit = ROOT / row["metadata"]["bundle"]
    dependencies = row["metadata"]["dependencies"]
    paths = [str(unit / "tests"), str(Path(row["query_path"]).parents[2])]
    # Resolve full fixed language/shared-library dependency closure.
    paths += [
        str(audit_settings.CODEQL_PACK_PATH / name / meta["version"])
        for name, meta in dependencies.items()
    ]
    runtime = None
    if row["language"] == "python":
        runtime = unit / "runtime"
        runtime.mkdir(exist_ok=True)
        interpreter = shutil.which(audit_settings.CODEQL_PYTHON_BIN)
        if not interpreter:
            raise AuditError("Python 抽取解释器不可用")
        alias = runtime / "python3"
        if not alias.exists():
            alias.symlink_to(interpreter)
    try:
        run_command(
            [
                audit_settings.CODEQL_BIN,
                "test",
                "run",
                f"--additional-packs={os.pathsep.join(paths)}",
                f"--ram={audit_settings.CODEQL_RAM}",
                str(unit / "tests" / Path(row["query_path"]).name),
            ],
            unit / "test-execution.log",
            audit_settings.SCAN_TIMEOUT,
            runtime_path=runtime,
        )
        return {
            "status": "passed",
            "kind": "official_development_test",
            "codeql": CodeQLScanner().version(),
        }
    except (AuditError, OSError) as exc:
        return {
            "status": "failed",
            "error": str(exc)[:1000],
            "kind": "official_development_test",
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--index", action="store_true")
    parser.add_argument("--per-language", type=int, default=10)
    args = parser.parse_args()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    manifest = {"commits": COMMITS, "reference": [], "rule_example": []}
    with httpx.Client(
        timeout=40, transport=httpx.HTTPTransport(retries=2), trust_env=False
    ) as client:
        for lang in ("python", "javascript"):
            manifest["reference"].extend(library_topics(lang))
            for row in collect_examples(lang, client, args.per_language):
                if args.validate:
                    row["metadata"]["validation"] = validate_example(row)
                original = (
                    ROOT / row["metadata"]["bundle"] / "original.ql"
                ).read_text()
                content = f"# {row['title']} ({lang}, {row['metadata']['cwe']})\nPinned API {row['metadata']['api_version']}. Official query reuse. Developer validation: {row['metadata']['validation']['status']}.\n```ql\n{original}\n```\n"
                record = import_knowledge(
                    None,
                    row["title"],
                    f"curated-codeql-example:{lang}/{Path(row['query_path']).name}",
                    lang,
                    content,
                    row["metadata"],
                    corpus="rule_example",
                )
                manifest["rule_example"].append({**row, **record})
                save_json(OUTPUT / "manifest.json", manifest)
                print(
                    json.dumps(
                        {
                            "language": lang,
                            "example": row["title"],
                            "validation": row["metadata"]["validation"]["status"],
                        }
                    ),
                    flush=True,
                )
    if args.index:
        from uuid import UUID

        for row in [*manifest["reference"], *manifest["rule_example"]]:
            index_document(UUID(row["document_id"]), None)
    save_json(OUTPUT / "manifest.json", manifest)
    print(
        json.dumps(
            {
                "reference_topics": len(manifest["reference"]),
                "complete_examples": len(manifest["rule_example"]),
                "passed_examples": sum(
                    r["metadata"]["validation"]["status"] == "passed"
                    for r in manifest["rule_example"]
                ),
            }
        )
    )


if __name__ == "__main__":
    main()
