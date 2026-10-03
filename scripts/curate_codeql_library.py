"""Second corpus revision: pinned library API sources, kept separate from baseline."""

import hashlib
import json
from pathlib import Path

from app.adapters.codeql.custom import fixed_dependencies
from app.adapters.retrieval.knowledge import import_knowledge
from app.core.audit_config import audit_settings

ROOT = Path(__file__).resolve().parents[1]


def main(owner=None):
    manifest = []
    for language in ("python", "javascript"):
        version = fixed_dependencies(language)[f"codeql/{language}-all"]["version"]
        root = audit_settings.CODEQL_PACK_PATH / f"codeql/{language}-all" / version
        folder = root / f"semmle/{language}/security/dataflow"
        for operation in ("CodeInjection", "SqlInjection", "ReflectedXss"):
            for suffix in ("Query", "Customizations"):
                path = folder / f"{operation}{suffix}.qll"
                if not path.exists() or path.stat().st_size > 7000:
                    continue
                raw = path.read_text()
                relative = path.relative_to(root).as_posix()
                content = f"# {language} eval SQL XSS {operation}{suffix} fixed dataflow API\nVersion {version}. This is a complete pinned library file, not a generated answer or independent test. Use proven exported Flow modules when the baseline already covers the requirement; do not invent conversions among AST Expr, control-flow nodes and DataFlow::Node. Explain that reusing baseline semantics is not new coverage.\n```ql\n{raw}\n```\n"
                provenance = {
                    "license": "MIT",
                    "license_source": "https://github.com/github/codeql/blob/main/LICENSE",
                    "trust": "pinned_codeql_library",
                    "api_version": version,
                    "source_sha256": hashlib.sha256(raw.encode()).hexdigest(),
                    "collected_date": "2026-10-03",
                }
                result = import_knowledge(
                    owner,
                    f"{language} {operation}{suffix} API",
                    f"codeql-pack:codeql/{language}-all@{version}/{relative}",
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
        if language == "python":
            path = root / "semmle/python/dataflow/new/internal/DataFlowPublic.qll"
            lines = path.read_text().splitlines()
            # Exact source range includes complete Node/CfgNode/CallCfgNode/ExprNode declarations.
            text = "\n".join(lines[147:294])
            content = f"# Python eval CodeQL AST and dataflow node conversion API\nFixed python-all@{version}, source excerpt DataFlowPublic.qll lines 148–294. This is a declaration excerpt, not a standalone query. AST Expr, control-flow nodes and DataFlow::Node are distinct. Follow the exact declarations below; do not invent conversion methods or cast unrelated node types.\n```ql\n{text}\n```\n"
            result = import_knowledge(
                owner,
                "Python AST dataflow conversion declarations",
                f"codeql-pack:codeql/python-all@{version}/DataFlowPublic.qll#L148-L294",
                "python",
                content,
                {
                    "license": "MIT",
                    "trust": "pinned_codeql_library",
                    "api_version": version,
                    "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "lines": [148, 294],
                },
            )
            manifest.append(
                {
                    "language": language,
                    "path": str(path.relative_to(root)),
                    "source_lines": [148, 294],
                    **result,
                }
            )
    (ROOT / "docs/research/codeql-library-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2)
    )
    print("Imported library revision", len(manifest))


if __name__ == "__main__":
    main()
