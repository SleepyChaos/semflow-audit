"""Collect exact local official sources without changing earlier frozen corpora."""

import hashlib
import json
import re
from pathlib import Path

import yaml
from app.adapters.codeql.custom import fixed_dependencies
from app.core.audit_config import audit_settings
from codeql_corpus_sources import COMMITS, ROOT, sha, source_tree

OUTPUT = ROOT / "artifacts/materials/rag-corpus-v3"
PREVIOUS = ROOT / "artifacts/materials/rag-corpus-v2/manifest.json"
FRAMEWORKS = {
    "python": [
        "Flask",
        "Django",
        "FastApi",
        "Starlette",
        "Aiohttp",
        "Tornado",
        "Bottle",
        "Sanic",
        "Werkzeug",
        "RestFramework",
        "SqlAlchemy",
        "FlaskSqlAlchemy",
        "PEP249",
        "Psycopg",
        "Psycopg2",
        "PyMySQL",
        "Mysql",
        "MySQLdb",
        "Sqlite3",
        "PyMongo",
        "Asyncpg",
        "Aiosqlite",
        "Requests",
        "Httpx",
        "Urllib3",
        "Jinja2",
        "Mako",
        "MarkupSafe",
        "Yaml",
        "JsonPickle",
        "Lxml",
        "Xmltodict",
        "Cryptography",
        "Paramiko",
        "Fabric",
        "Invoke",
        "Dill",
        "Joblib",
    ],
    "javascript": [
        "Express",
        "ExpressModules",
        "Koa",
        "Fastify",
        "Hapi",
        "Nest",
        "Next",
        "React",
        "Vue",
        "AngularJS",
        "Angular2",
        "HTTP",
        "HttpFrameworks",
        "FormParsers",
        "SQL",
        "Knex",
        "NoSQL",
        "NodeJSLib",
        "Files",
        "ClientRequests",
        "Request",
        "SystemCommandExecutors",
        "ShellJS",
        "Templating",
        "Handlebars",
        "Markdown",
        "jQuery",
        "DOM",
        "JWT",
        "CookieLibraries",
        "CryptoLibraries",
        "XmlParsers",
        "GraphQL",
        "SocketIO",
        "WebSocket",
        "Electron",
        "LodashUnderscore",
        "TrustedTypes",
        "ServerLess",
    ],
}


def verify(path, root, prefix, tree):
    content = path.read_bytes()
    relative = path.relative_to(root).as_posix()
    blob = hashlib.sha1(
        b"blob " + str(len(content)).encode() + b"\0" + content
    ).hexdigest()
    if tree.get(prefix + relative, {}).get("sha") != blob:
        raise ValueError(f"Installed source differs from pinned tree: {relative}")
    return content.decode(), relative


def references(language):
    deps = fixed_dependencies(language)
    version = deps[f"codeql/{language}-all"]["version"]
    root = audit_settings.CODEQL_PACK_PATH / f"codeql/{language}-all" / version
    base = root / f"semmle/{language}"
    tree = {r["path"]: r for r in source_tree(language)["tree"]}
    paths = list((base / "security/dataflow").glob("*.qll"))
    paths += [base / "frameworks" / (name + ".qll") for name in FRAMEWORKS[language]]
    paths += list((base / "dataflow/new").glob("*.qll"))
    paths += [base / "dataflow" / (n + ".qll") for n in ["DataFlow", "TaintTracking"]]
    paths += [base / (n + ".qll") for n in ["ApiGraphs", "Concepts"]]
    rows = []
    for path in sorted(set(paths)):
        if not path.is_file():
            continue
        text, relative = verify(path, root, "ql/lib/", tree)
        destination = OUTPUT / "reference" / language / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(text)
        source = f"pinned-codeql-library:codeql/{language}-all@{version}/{relative}"
        metadata = {
            "trust": "pinned_codeql_source",
            "license": "MIT",
            "license_source": f"https://github.com/github/codeql/blob/{COMMITS[language]}/LICENSE",
            "commit": COMMITS[language],
            "source_url": f"https://github.com/github/codeql/blob/{COMMITS[language]}/{language}/ql/lib/{relative}",
            "api_version": version,
            "library_pack": f"codeql/{language}-all@{version}",
            "source_sha256": sha(text),
            "original_path": str(destination.relative_to(ROOT)),
            "validation": "Exact library source; API references are not independently verified detectors",
        }
        rows.append(
            {
                "language": language,
                "topic": path.stem,
                "title": f"{language} {path.stem} API",
                "source": source,
                "metadata": metadata,
                "content": f"# {language} {path.stem} API ({version})\nSource: {metadata['library_pack']}/{relative}\n\n{text}",
            }
        )
    return rows


def local_modules(query, root, tree):
    """Retain relative query helpers transitively; library imports stay pinned dependencies."""
    modules, pending = {}, [query]
    while pending:
        path = pending.pop()
        for token in re.findall(
            r"^(?:private\s+|public\s+)?import\s+([A-Za-z_][A-Za-z0-9_.]*)",
            path.read_text(),
            re.MULTILINE,
        ):
            suffix = Path(token.replace(".", "/") + ".qll")
            candidates = [path.parent / suffix, root / suffix]
            target = next((p for p in candidates if p.is_file()), None)
            if target is None:
                continue
            target = target.resolve()
            relative = target.relative_to(root.resolve()).as_posix()
            if relative in modules:
                continue
            text, _ = verify(target, root.resolve(), "ql/src/", tree)
            modules[relative] = text
            pending.append(target)
    return modules


def examples(language):
    name, version = getattr(audit_settings, language.upper() + "_QUERY_PACK").split("@")
    root = audit_settings.CODEQL_PACK_PATH / name / version
    tree = {r["path"]: r for r in source_tree(language)["tree"]}
    deps = fixed_dependencies(language)
    pack = OUTPUT / "compile" / language
    pack.mkdir(parents=True, exist_ok=True)
    (pack / "qlpack.yml").write_text(
        yaml.safe_dump(
            {
                "name": f"audit/corpus-{language}",
                "version": "0.0.1",
                "dependencies": {
                    f"codeql/{language}-all": deps[f"codeql/{language}-all"]["version"]
                },
            }
        )
    )
    (pack / "codeql-pack.lock.yml").write_text(
        yaml.safe_dump({"lockVersion": "1.0.0", "dependencies": deps})
    )
    rows, skipped = [], []
    for query in sorted(root.glob("Security/CWE-*/*.ql")):
        text, relative = verify(query, root, "ql/src/", tree)
        modules = local_modules(query, root, tree)
        title = re.search(r"@name\s+(.+)", text)
        if not title:
            skipped.append({"query": relative, "reason": "missing_name"})
            continue
        blocks = [
            f"# {title[1]} ({language}, {query.parent.name})\nPinned official query; independent task effectiveness not evaluated.\n```ql\n{text}\n```\n"
        ]
        blocks += [
            f"# Module {path}\n```ql\n{body}\n```\n" for path, body in modules.items()
        ]
        content = "\n".join(blocks)
        if any(len(block) > 8000 for block in blocks) or len(content) > 18000:
            skipped.append(
                {
                    "query": relative,
                    "reason": "complete_bundle_exceeds_existing_context_contract",
                    "characters": len(content),
                }
            )
            continue
        target = pack / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
        for path, body in modules.items():
            dest = pack / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(body)
        metadata = {
            "trust": "pinned_codeql_source",
            "license": "MIT",
            "license_source": f"https://github.com/github/codeql/blob/{COMMITS[language]}/LICENSE",
            "commit": COMMITS[language],
            "source_url": f"https://github.com/github/codeql/blob/{COMMITS[language]}/{language}/ql/src/{relative}",
            "source_sha256": sha(text),
            "api_version": deps[f"codeql/{language}-all"]["version"],
            "query_pack": name + "@" + version,
            "dependencies": deps,
            "cwe": query.parent.name,
            "imports": re.findall(r"^import (.+)$", text, re.MULTILINE),
            "bundle": str(pack.relative_to(ROOT)),
            "entrypoint": relative,
            "modules": {p: sha(body) for p, body in modules.items()},
            "validation": {"status": "not_run"},
            "meaning": "Exact complete query and local helpers; compiler-only validation is not developer or holdout effectiveness",
        }
        rows.append(
            {
                "language": language,
                "title": title[1],
                "source": f"curated-codeql-example:{language}/{query.name}",
                "query_path": str(target),
                "metadata": metadata,
                "content": content,
            }
        )
    return rows, skipped


def previous():
    return json.loads(PREVIOUS.read_text())
