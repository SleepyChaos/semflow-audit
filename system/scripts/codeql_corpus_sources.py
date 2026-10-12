"""Pinned public CodeQL API references and exact Git-blob downloads."""

import hashlib
import json
import re
from pathlib import Path

import httpx
from app.adapters.codeql.custom import fixed_dependencies
from app.adapters.retrieval.knowledge import import_knowledge
from app.core.audit_config import audit_settings

ROOT = Path(__file__).resolve().parents[2]
COMMITS = {
    "python": "4ece8abc3032a266eb4b9839442d8be5084552ea",
    "javascript": "c524a98eb91c769cb2994b8373181c2ebd27c20f",
}
OUTPUT = ROOT / "artifacts/materials/rag-corpus-v2"


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def library_topics(language):
    version = fixed_dependencies(language)[f"codeql/{language}-all"]["version"]
    root = audit_settings.CODEQL_PACK_PATH / f"codeql/{language}-all" / version
    security = root / f"semmle/{language}/security/dataflow"
    wanted = [
        "CodeInjection",
        "SqlInjection",
        "CommandInjection",
        "PathInjection",
        "ReflectedXSS" if language == "python" else "ReflectedXss",
        "ServerSideRequestForgery"
        if language == "python"
        else "ClientSideRequestForgery",
        "UnsafeDeserialization",
    ]
    selected = [p for topic in wanted for p in sorted(security.glob(topic + "*.qll"))]
    framework = root / f"semmle/{language}/frameworks"
    names = (
        ["Flask", "Django", "SqlAlchemy", "Stdlib", "Requests"]
        if language == "python"
        else ["Express", "SQL", "HTTP", "SystemCommandExecutors", "Templating"]
    )
    selected += [
        framework / (name + ".qll")
        for name in names
        if (framework / (name + ".qll")).exists()
    ]
    selected += [
        p
        for p in sorted((root / f"semmle/{language}/dataflow").glob("*.qll"))
        if p.name in {"DataFlow.qll", "TaintTracking.qll"}
    ]
    tree = source_tree(language)
    by_path = {e["path"]: e for e in tree["tree"]}
    api_graph = root / f"semmle/{language}/ApiGraphs.qll"
    if api_graph.is_file():
        selected.append(api_graph)
    results = []
    for path in dict.fromkeys(selected):
        text = path.read_text()
        relative = path.relative_to(root).as_posix()
        blob = path.read_bytes()
        if (
            by_path.get("ql/lib/" + relative, {}).get("sha")
            != hashlib.sha1(
                b"blob " + str(len(blob)).encode() + b"\0" + blob
            ).hexdigest()
        ):
            raise ValueError(
                "Installed API source differs from fixed pack build commit"
            )
        original = OUTPUT / "reference" / language / relative
        original.parent.mkdir(parents=True, exist_ok=True)
        original.write_text(text)
        metadata = {
            "trust": "pinned_codeql_source",
            "license": "MIT",
            "license_source": "https://github.com/github/codeql/blob/"
            + COMMITS[language]
            + "/LICENSE",
            "commit": COMMITS[language],
            "source_url": f"https://github.com/github/codeql/blob/{COMMITS[language]}/{language}/ql/lib/{relative}",
            "api_version": version,
            "library_pack": f"codeql/{language}-all@{version}",
            "source_sha256": sha(text),
            "original_path": str(original.relative_to(ROOT)),
            "validation": "Exact library source; fragments are API reference, not independently verified detectors",
        }
        # Plain source stays exactly available as an original file; no half query is a rule example.
        content = f"# {language} {path.stem} API ({version})\nSource: {metadata['library_pack']}/{relative}\n\n{text}"
        record = import_knowledge(
            None,
            f"{language} {path.stem} API",
            "pinned-codeql-library:" + metadata["library_pack"] + "/" + relative,
            language,
            content,
            metadata,
            corpus="reference",
            content_format="source",
        )
        results.append(
            {"language": language, "topic": path.stem, "metadata": metadata, **record}
        )
    return results


def download(client, language, entry, destination):
    url = f"https://raw.githubusercontent.com/github/codeql/{COMMITS[language]}/{language}/{entry['path']}"
    candidates = [destination]
    for version in ("rag-corpus-v4", "rag-corpus-v3", "rag-corpus-v2", "rag-corpus-v1"):
        candidates.append(Path(re.sub(r"rag-corpus-v[1-4]", version, str(destination))))
    cached = next((p for p in candidates if p.is_file()), destination)
    if cached.is_file():
        blob = cached.read_bytes()
        expected = hashlib.sha1(
            b"blob " + str(len(blob)).encode() + b"\0" + blob
        ).hexdigest()
    else:
        expected = None
    if expected != entry["sha"]:
        for attempt in range(3):
            try:
                response = client.get(url)
                response.raise_for_status()
                blob = response.content
                break
            except (httpx.TransportError, httpx.HTTPStatusError):
                if attempt == 2:
                    raise
    actual = hashlib.sha1(b"blob " + str(len(blob)).encode() + b"\0" + blob).hexdigest()
    if actual != entry["sha"]:
        raise ValueError("Official source changed from frozen tree")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(blob)
    return {
        "url": url,
        "path": str(destination.relative_to(OUTPUT)),
        "sha256": hashlib.sha256(blob).hexdigest(),
    }


def source_tree(language):
    """Fetch a complete per-language tree; the top recursive GitHub tree truncates."""
    path = ROOT / f"artifacts/materials/{language}-tree-pack.json"
    if path.is_file():
        saved = json.loads(path.read_text())
        if saved.get("commit") == COMMITS[language] and not saved.get("truncated"):
            return saved
    with httpx.Client(
        timeout=40, transport=httpx.HTTPTransport(retries=2), trust_env=False
    ) as client:
        response = client.get(
            "https://api.github.com/repos/github/codeql/git/trees/" + COMMITS[language]
        )
        response.raise_for_status()
        subtree = next(
            entry["sha"]
            for entry in response.json()["tree"]
            if entry["path"] == language
        )
        response = client.get(
            "https://api.github.com/repos/github/codeql/git/trees/" + subtree,
            params={"recursive": 1},
        )
        response.raise_for_status()
        tree = response.json()
    if tree.get("truncated"):
        raise ValueError(
            "Official per-language tree truncated; cannot prove complete materials"
        )
    tree["commit"] = COMMITS[language]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(tree))
    return tree
