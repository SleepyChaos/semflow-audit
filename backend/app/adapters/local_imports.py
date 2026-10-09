"""Bounded Python import navigation using AST; never execute target modules."""

import ast
from pathlib import Path


def python_import_paths(
    root: Path, file: str, body: str, allowed: set[str]
) -> list[str]:
    try:
        tree = ast.parse(body)
    except SyntaxError:
        return []
    modules = []
    parent = Path(file).parent
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(Path(*a.name.split(".")) for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = parent
            if node.level:
                for _ in range(node.level - 1):
                    base = base.parent
            else:
                base = Path(".")
            module = base / Path(*(node.module or "").split("."))
            modules.append(module)
            modules.extend(module / a.name for a in node.names if a.name != "*")
    found = []
    for module in modules:
        for relative in (module.with_suffix(".py"), module / "__init__.py"):
            path = (root / relative).resolve()
            if path.is_relative_to(root.resolve()):
                name = path.relative_to(root.resolve()).as_posix()
                if name in allowed and path.is_file():
                    found.append(name)
    return list(dict.fromkeys(found))


def python_web_entrypoint(body: str) -> bool:
    """A real imported factory call is a navigation clue, not middleware proof."""
    try:
        tree = ast.parse(body)
    except SyntaxError:
        return False
    imports = set()
    modules = {}
    factories = {
        "flask": {"Flask"},
        "fastapi": {"FastAPI"},
        "aiohttp.web": {"Application"},
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module in factories:
            imports |= {
                a.asname or a.name
                for a in node.names
                if a.name in factories[node.module]
            }
        elif isinstance(node, ast.Import):
            modules.update({a.asname or a.name: a.name for a in node.names})
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name) and node.func.id in imports:
            return True
        if isinstance(node.func, ast.Attribute) and isinstance(
            node.func.value, ast.Name
        ):
            module = modules.get(node.func.value.id)
            if node.func.attr in factories.get(module, set()):
                return True
    return False
