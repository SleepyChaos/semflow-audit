"""Observe the shell option selected at an unambiguous Python call site."""

import ast


def selection(tree, call):
    func = call.func
    if not (
        isinstance(func, ast.Attribute)
        and func.attr == "run"
        and isinstance(func.value, ast.Name)
        and len(call.args) == 1
        and not isinstance(call.args[0], ast.Starred)
        and all(keyword.arg is not None for keyword in call.keywords)
    ):
        return None

    name = func.value.id
    imports = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        and any((a.asname or a.name.split(".")[0]) in {name, "*"} for a in node.names)
    ]
    if len(imports) != 1:
        return None
    declaration = imports[0]
    if not (
        isinstance(declaration, ast.Import)
        and declaration in tree.body
        and declaration.end_lineno < call.lineno
        and any(
            a.name == "subprocess" and (a.asname or a.name) == name
            for a in declaration.names
        )
    ) or _rebound(tree, name):
        return None

    shell = [item.value for item in call.keywords if item.arg == "shell"]
    if not shell:
        return "default_off", declaration.lineno
    if (
        len(shell) == 1
        and isinstance(shell[0], ast.Constant)
        and type(shell[0].value) is bool
    ):
        return "explicit_on" if shell[0].value else "explicit_off", declaration.lineno
    return None


def _rebound(tree, name):
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Name)
            and node.id == name
            and not isinstance(node.ctx, ast.Load)
        ):
            return True
        if isinstance(node, ast.arg) and node.arg == name:
            return True
        if (
            isinstance(
                node,
                (
                    ast.ClassDef,
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                    ast.ExceptHandler,
                    ast.MatchAs,
                    ast.MatchStar,
                ),
            )
            and node.name == name
        ):
            return True
        if (
            isinstance(node, ast.Attribute)
            and node.attr == "run"
            and isinstance(node.value, ast.Name)
            and node.value.id == name
            and not isinstance(node.ctx, ast.Load)
        ):
            return True
    return False
