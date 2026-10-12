"""Parse only: sample checking never executes generated Python or JavaScript."""

import ast
from pathlib import Path

import tree_sitter_javascript
import tree_sitter_typescript
from tree_sitter import Language, Parser

from app.domain.audit import AuditError


def check_syntax(name: str, content: str) -> None:
    suffix = Path(name).suffix
    if suffix == ".py":
        try:
            ast.parse(content, filename=name)
        except (SyntaxError, RecursionError) as exc:
            raise AuditError(f"样本语法无效：{name}") from exc
        return
    if suffix in {".ts", ".tsx"}:
        grammar = (
            tree_sitter_typescript.language_tsx()
            if suffix == ".tsx"
            else tree_sitter_typescript.language_typescript()
        )
    else:
        grammar = tree_sitter_javascript.language()
    parser = Parser(Language(grammar))
    if parser.parse(content.encode()).root_node.has_error:
        raise AuditError(f"样本语法无效：{name}")
