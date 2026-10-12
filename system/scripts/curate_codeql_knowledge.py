"""Import pinned local CodeQL query references; no holdout labels are indexed."""

import hashlib
import json
import re
from pathlib import Path

from app.adapters.codeql.custom import fixed_dependencies
from app.adapters.retrieval.knowledge import import_knowledge
from app.core.audit_config import audit_settings

ROOT = Path(__file__).resolve().parents[2]


def main():
    manifest = []
    for language in ("python", "javascript"):
        specification = getattr(audit_settings, language.upper() + "_QUERY_PACK")
        name, version = specification.split("@")
        root = audit_settings.CODEQL_PACK_PATH / name / version
        library_version = fixed_dependencies(language)[f"codeql/{language}-all"][
            "version"
        ]
        priority = [
            "CWE-094",
            "CWE-089",
            "CWE-079",
            "CWE-078",
            "CWE-022",
            "CWE-502",
            "CWE-918",
            "CWE-798",
            "CWE-020",
            "CWE-601",
        ]
        queries = sorted(
            (root / "Security").glob("CWE-*/*.ql"),
            key=lambda p: (
                priority.index(p.parent.name) if p.parent.name in priority else 100,
                p.name,
            ),
        )
        selected = []
        categories = set()
        for path in queries:
            if path.parent.name not in categories and path.stat().st_size < 7000:
                categories.add(path.parent.name)
                selected.append(path)
            if len(selected) == 10:
                break
        for path in selected:
            query = path.read_text()
            relative = path.relative_to(root).as_posix()
            title = re.search(r"@name (.+)", query)[1]
            provenance = {
                "license": "MIT",
                "license_source": "https://github.com/github/codeql/blob/main/LICENSE",
                "trust": "pinned_codeql_source",
                "api_version": library_version,
                "query_pack": specification,
                "source_sha256": hashlib.sha256(query.encode()).hexdigest(),
                "cwe": path.parent.name,
                "collected_date": "2026-10-03",
            }
            content = f"# {title} ({language}, {path.parent.name})\nFixed query pack: {specification}; language API: {library_version}. This official query illustrates its own semantics. It does not establish new framework coverage or independent validation of a generated query. Imports and PathGraph types must match the fixed library version.\n```ql\n{query}\n```\n"
            result = import_knowledge(
                None,
                title,
                f"codeql-pack:{specification}/{relative}",
                language,
                content,
                provenance,
            )
            manifest.append(
                {
                    "language": language,
                    "path": relative,
                    "provenance": provenance,
                    **result,
                }
            )
        seed = ROOT / "system/knowledge" / f"{language}-codeql.md"
        import_knowledge(
            None,
            f"{language} project rule guide",
            f"project-maintained:{seed.name}",
            language,
            seed.read_text(),
            {
                "license": "project-maintained",
                "trust": "project_example",
                "api_version": library_version,
            },
        )
    (ROOT / "research/catalog/codeql-knowledge-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2)
    )
    print(f"Imported {len(manifest)} pinned references + two project guides")


if __name__ == "__main__":
    main()
