"""Conservative AST binding clues; never a resolved runtime call graph."""

import ast
import builtins


def names_in_scope(nodes):
    names = set()
    dynamic = False
    for node in nodes:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
            continue
        if isinstance(node, ast.Import):
            names.update(a.asname or a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.update(a.asname or a.name for a in node.names)
            dynamic |= any(a.name == "*" for a in node.names)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            names.add(node.id)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            dynamic |= node.func.id in {"exec", "eval", "globals", "locals"}
        if not isinstance(
            node,
            (ast.Lambda, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp),
        ):
            child_names, child_dynamic = names_in_scope(ast.iter_child_nodes(node))
            names |= child_names
            dynamic |= child_dynamic
    return names, dynamic


def binding_clues(source, line):
    try:
        tree = ast.parse(source)
    except SyntaxError, ValueError, RecursionError:
        return {"status": "unavailable", "reason": "AST parse failed"}
    scopes = [
        n
        for n in ast.walk(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        and n.lineno <= line <= n.end_lineno
    ]
    scopes.sort(key=lambda n: n.end_lineno - n.lineno, reverse=True)
    names, dynamic = names_in_scope(tree.body)
    for scope in scopes:
        local, uncertain = names_in_scope(scope.body)
        local.update(
            a.arg
            for a in [*scope.args.posonlyargs, *scope.args.args, *scope.args.kwonlyargs]
        )
        local.update(a.arg for a in (scope.args.vararg, scope.args.kwarg) if a)
        names |= local
        dynamic |= uncertain
    calls = sorted(
        {
            n.func.id
            for n in ast.walk(tree)
            if isinstance(n, ast.Call)
            and n.lineno <= line <= n.end_lineno
            and isinstance(n.func, ast.Name)
        }
    )
    return {
        "status": "syntactic_clues",
        "line": line,
        "direct_calls": [
            {
                "name": name,
                "binding": "declared_in_scope"
                if name in names
                else "builtin"
                if name in vars(builtins)
                else "unknown_dynamic_scope"
                if dynamic
                else "no_static_binding",
            }
            for name in calls
        ],
        "limit": "AST declarations are not runtime dispatch or reachability proof; unbound names must not be invented as imported aliases",
    }


def location_bindings(evidence, locations):
    result = []
    for location in locations:
        file = location["file"]
        if not file.endswith(".py"):
            continue
        path = evidence.allowed(file)
        if path.stat().st_size > 200000:
            result.append(
                {
                    "file": file,
                    "status": "unavailable",
                    "reason": "binding input exceeds bound",
                }
            )
            continue
        result.append(
            {"file": file, **binding_clues(path.read_text(), location["line"])}
        )
    return result


def window_bindings(evidence, reference):
    if not reference["file"].endswith(".py"):
        return []
    path = evidence.allowed(reference["file"])
    if path.stat().st_size > 200000:
        return []
    source = path.read_text()
    try:
        lines = sorted(
            {
                n.lineno
                for n in ast.walk(ast.parse(source))
                if isinstance(n, ast.Call)
                and isinstance(n.func, ast.Name)
                and reference["start_line"] <= n.lineno <= reference["end_line"]
            }
        )
    except SyntaxError, ValueError, RecursionError:
        return []
    return [
        {"file": reference["file"], **binding_clues(source, line)}
        for line in lines[:24]
    ]


def unbound_operation(evidence, location, weakness):
    if weakness not in {"CWE-78", "CWE-078", "CWE-94", "CWE-094", "CWE-95", "CWE-095"}:
        return False
    return any(
        c["binding"] == "no_static_binding"
        for clue in location_bindings(evidence, [location])
        for c in clue.get("direct_calls", [])
    )
