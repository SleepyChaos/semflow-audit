"""Seed fixed-version RAG collections without model calls or source uploads.

Official queries are compiled before indexing. Compile-only provenance does not
claim regression accuracy or independent validation. Imports are idempotent.
"""

import hashlib
import re

from app.adapters.codeql.custom import compile_query, fixed_dependencies, prepare_query
from app.adapters.retrieval.knowledge import import_knowledge
from app.core.audit_config import audit_settings


def metadata(language):
    spec = (
        audit_settings.PYTHON_QUERY_PACK
        if language == "python"
        else audit_settings.JAVASCRIPT_QUERY_PACK
    )
    return {
        "trust": "pinned_codeql_source",
        "license": "MIT",
        "query_pack": spec,
        "api_version": fixed_dependencies(language)[f"codeql/{language}-all"][
            "version"
        ],
    }


def seed_references(language):
    info = metadata(language)
    root = (
        audit_settings.CODEQL_PACK_PATH / f"codeql/{language}-all" / info["api_version"]
    )
    library = root / f"semmle/{language}"
    files = [library / "ApiGraphs.qll", *list((library / "dataflow").glob("*.qll"))]
    for topic in ["CodeInjection", "SqlInjection", "ReflectedXss", "ReflectedXSS"]:
        files.extend((library / "security/dataflow").glob(topic + "*.qll"))
    for framework in ["Flask", "Django", "Express"]:
        files.append(library / "frameworks" / (framework + ".qll"))
    for path in dict.fromkeys(files):
        if not path.is_file():
            continue
        content = path.read_text()
        import_knowledge(
            None,
            path.stem,
            f"container-pack:{language}/{path.relative_to(root)}",
            language,
            content,
            {**info, "source_sha256": hashlib.sha256(content.encode()).hexdigest()},
            corpus="reference",
            content_format="source",
        )


def seed_examples():
    paths = [
        "CWE-094/CodeInjection.ql",
        "CWE-089/SqlInjection.ql",
        "CWE-079/ReflectedXss.ql",
    ]
    for language in ("python", "javascript"):
        info = metadata(language)
        name, version = info["query_pack"].split("@")
        root = audit_settings.CODEQL_PACK_PATH / name / version / "Security"
        for relative in paths:
            print(f"Compile RAG example: {language}/{relative}", flush=True)
            original = (root / relative).read_text()
            seed_example(language, relative, original, info)


def seed_example(language, relative, original, info):
    identifier = language + "-" + relative.split("/")[0]
    pack = audit_settings.ARTIFACT_ROOT / "bootstrap" / identifier
    query = re.sub(
        r"@id\s+[^\n]+", f"@id custom/container/{identifier.lower()}", original
    )
    prepare_query(pack, language, query, {}, fixed_dependencies(language))
    compile_query(pack, pack / "compile.log")
    cwes = [
        f"CWE-{int(value):03d}"
        for value in re.findall(r"external/cwe/cwe-(\d+)", original)
    ]
    import_knowledge(
        None,
        relative,
        f"container-example:{language}/{relative}",
        language,
        original,
        {
            **info,
            "cwe": cwes[0],
            "cwe_ids": cwes,
            "source_sha256": hashlib.sha256(original.encode()).hexdigest(),
            "validation": {"status": "passed", "kind": "compile_only"},
            "meaning": "Pinned official query; compile only, not accuracy evidence",
        },
        corpus="rule_example",
    )


if __name__ == "__main__":
    for language in ("python", "javascript"):
        seed_references(language)
    seed_examples()
    print("Seeded fixed-version RAG reference and rule-example collections", flush=True)
