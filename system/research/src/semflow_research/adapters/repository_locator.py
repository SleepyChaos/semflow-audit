"""Bounded, read-only cross-language navigation within an authorized snapshot."""

import ast
import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path, PurePosixPath
from time import monotonic

from semflow_research.adapters.source_inventory import (
    CONFIG,
    TEMPLATES,
    category,
    readable_name,
)
from semflow_research.domain.errors import AuditError

LANGUAGES = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".java": "java",
    ".go": "go",
    ".rb": "ruby",
    ".php": "php",
    ".cs": "csharp",
    ".rs": "rust",
    ".kt": "kotlin",
    ".scala": "scala",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".sql": "sql",
    ".graphql": "graphql",
    ".gql": "graphql",
    ".md": "text",
    ".txt": "text",
    **dict.fromkeys(TEMPLATES, "template"),
    **dict.fromkeys(CONFIG, "config"),
}
_MAX_FILE = 1024 * 1024
_MAX_BYTES = 32 * _MAX_FILE
_MAX_FILES = 4000


def repository_text(file: str) -> bool:
    language = LANGUAGES.get(PurePosixPath(file).suffix.lower())
    return readable_name(file) and language not in {None, "text"}


@dataclass(frozen=True)
class RepositoryMatch:
    file: str
    start_line: int
    end_line: int
    content: str
    kind: str
    language: str


@dataclass(frozen=True)
class RepositorySearch:
    matches: tuple[RepositoryMatch, ...]
    truncated: bool


class RepositoryLocator:
    def __init__(self, root: Path, allowed: Callable[[str], Path]):
        self.root = root.resolve()
        self.allowed = allowed

    def _files(self, scope: tuple[str, ...], extensions: tuple[str, ...]) -> Iterator:
        for path in sorted(
            self.root.rglob("*"),
            key=lambda item: (_test_path(item.relative_to(self.root)), item),
        ):
            if path.is_symlink() or not path.is_file():
                continue
            relative = path.relative_to(self.root).as_posix()
            if not readable_name(relative):
                continue
            explicit = relative in scope
            if scope and not any(
                PurePosixPath(relative).is_relative_to(p) for p in scope
            ):
                continue
            suffix = path.suffix.lower()
            if extensions and suffix not in extensions:
                continue
            if not explicit and (
                suffix not in LANGUAGES
                or category(relative) == "third_party_or_generated"
            ):
                continue
            try:
                authorized = self.allowed(relative)
            except AuditError as exc:
                if exc.code in {"identity_error", "integrity_error"}:
                    raise
                continue
            if authorized.resolve() != path:
                continue
            yield relative, path, LANGUAGES.get(suffix, "text")

    def find_paths(self, name: str, *, limit: int = 20) -> RepositorySearch:
        token = name.replace("\\", "/")
        path = PurePosixPath(token)
        if not token or path.is_absolute() or ".." in path.parts or ":" in token:
            return RepositorySearch((), False)
        hits = []
        for rel, _, language in self._files((), ()):
            if PurePosixPath(rel).name.casefold() != path.name.casefold():
                continue
            hits.append(RepositoryMatch(rel, 1, 1, "", "path", language))
        hits.sort(key=lambda h: (h.file != token, h.file.count("/"), h.file))
        return RepositorySearch(tuple(hits[:limit]), len(hits) > limit)

    def search_code(
        self,
        query: str,
        *,
        scope: tuple[str, ...] = (),
        extensions: tuple[str, ...] = (),
        limit: int = 20,
        file_pattern: str | None = None,
    ) -> RepositorySearch:
        return self._search(query, "text", scope, extensions, limit, file_pattern)

    def find_symbol(
        self,
        symbol: str,
        *,
        scope: tuple[str, ...] = (),
        limit: int = 20,
    ) -> RepositorySearch:
        return self._search(symbol, "definition", scope, (), limit)

    def find_references(
        self,
        symbol: str,
        *,
        scope: tuple[str, ...] = (),
        limit: int = 20,
    ) -> RepositorySearch:
        return self._search(symbol, "reference", scope, (), limit)

    def _search(
        self,
        query: str,
        mode: str,
        scope: tuple[str, ...],
        extensions: tuple[str, ...],
        limit: int,
        file_pattern: str | None = None,
    ) -> RepositorySearch:
        if not query or len(query) > 200 or not 1 <= limit <= 40:
            raise ValueError("Invalid repository search size")
        if mode != "text" and not re.fullmatch(r"[A-Za-z_$][\w$]*", query):
            return RepositorySearch((), False)
        matches, lexical = [], []
        size, limited, started = 0, False, monotonic()
        for count, (relative, path, language) in enumerate(
            self._files(scope, extensions)
        ):
            if count >= _MAX_FILES or size >= _MAX_BYTES or monotonic() - started > 5:
                limited = True
                break
            if file_pattern and not fnmatchcase(relative, file_pattern):
                continue
            try:
                count_bytes = path.stat().st_size
                if count_bytes > _MAX_FILE:
                    limited = True
                    continue
                size += count_bytes
                source = path.read_text(encoding="utf-8-sig")
            except (OSError, UnicodeError):
                limited = True
                continue
            if query not in source:
                continue
            lines = source.splitlines()
            for start, end, kind in _locations(query, mode, language, source, lines):
                bucket = (
                    lexical
                    if kind == "text_reference" and mode == "definition"
                    else matches
                )
                if len(bucket) <= limit:
                    bucket.append(
                        RepositoryMatch(
                            relative, start, end, lines[start - 1][:300], kind, language
                        )
                    )
            if mode != "definition" and len(matches) > limit:
                break
        found = matches if matches or mode != "definition" else lexical
        if mode == "definition":
            found.sort(
                key=lambda hit: (
                    _test_path(PurePosixPath(hit.file)),
                    hit.kind == "related_definition",
                    hit.file,
                    hit.start_line,
                )
            )
        return RepositorySearch(tuple(found[:limit]), limited or len(found) > limit)


def _locations(query, mode, language, source, lines):
    symbol = re.escape(query)
    word = re.compile(rf"(?<![\w$]){symbol}(?![\w$])")
    if mode == "text":
        for number, line in enumerate(lines, 1):
            if query in line:
                yield number, number, "text_match"
        return
    if mode == "definition" and language == "python":
        yield from _python_definitions(query, source)
    js_def = re.compile(
        rf"(?:\bfunction\s*\*?\s*{symbol}\s*\(|"
        rf"\b(?:const|let|var)\s+{symbol}(?:\s*:\s*[^=]+)?\s*=\s*"
        r"(?:async\s+)?(?:function\b|[^;]*=>))"
    )
    for number, line in enumerate(lines, 1):
        if not word.search(line):
            continue
        if (
            mode == "definition"
            and language in {"javascript", "typescript"}
            and js_def.search(line.split("//", 1)[0])
        ):
            yield number, number, "lexical_definition"
        elif (
            mode != "definition"
            or language != "javascript"
            or not line.lstrip().startswith("//")
        ):
            yield number, number, "text_reference"


def _test_path(path: Path) -> bool:
    return (
        bool({"test", "tests", "__tests__"} & set(path.parts))
        or path.stem.startswith("test_")
        or path.stem.endswith("_test")
    )


def _python_definitions(query: str, source: str):
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError, RecursionError):
        return
    for node in ast.walk(tree):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == query:
                yield node.lineno, node.end_lineno or node.lineno, "syntax_definition"
            elif node.name.endswith("_" + query):
                # A route may name a decorated handler differently. A suffix
                # match is a navigation candidate, never proof of dispatch.
                yield node.lineno, node.end_lineno or node.lineno, "related_definition"
    for node in tree.body:
        names = (
            node.targets
            if isinstance(node, ast.Assign)
            else ([node.target] if isinstance(node, ast.AnnAssign) else [])
        )
        if any(isinstance(name, ast.Name) and name.id == query for name in names):
            yield node.lineno, node.end_lineno or node.lineno, "syntax_definition"
