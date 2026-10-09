"""Bounded framework route syntax from mature parsers; not resolved request reachability."""

import ast
import hashlib

METHODS = {"get", "post", "put", "delete", "patch", "head", "options", "all", "route"}


def python_routes(text):
    try:
        tree = ast.parse(text)
    except SyntaxError, ValueError:
        return []
    rows = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if (
                not isinstance(decorator, ast.Call)
                or not isinstance(decorator.func, ast.Attribute)
                or decorator.func.attr not in METHODS
            ):
                continue
            if (
                not decorator.args
                or not isinstance(decorator.args[0], ast.Constant)
                or not isinstance(decorator.args[0].value, str)
            ):
                continue
            methods = (
                [decorator.func.attr.upper()]
                if decorator.func.attr != "route"
                else ["GET"]
            )
            for keyword in decorator.keywords:
                if keyword.arg == "methods" and isinstance(
                    keyword.value, (ast.List, ast.Tuple)
                ):
                    methods = [
                        value.value
                        for value in keyword.value.elts
                        if isinstance(value, ast.Constant)
                        and isinstance(value.value, str)
                    ]
            rows.append(
                {
                    "endpoint": decorator.args[0].value,
                    "methods": methods,
                    "start_line": decorator.lineno,
                    "end_line": node.end_lineno,
                    "handler": node.name,
                    "route_quote": ast.get_source_segment(text, decorator)[:300],
                }
            )
    return rows


def javascript_routes(text):
    import tree_sitter_javascript
    from tree_sitter import Language, Parser

    parser = Parser(Language(tree_sitter_javascript.language()))
    tree = parser.parse(text.encode())
    rows = []
    queue = [tree.root_node]
    while queue:
        node = queue.pop()
        queue.extend(reversed(node.named_children))
        if node.type != "call_expression":
            continue
        function = node.child_by_field_name("function")
        arguments = node.child_by_field_name("arguments")
        if not function or function.type != "member_expression" or not arguments:
            continue
        prop = function.child_by_field_name("property")
        if not prop or prop.text.decode() not in METHODS:
            continue
        args = arguments.named_children
        if not args or args[0].type != "string":
            continue
        path = args[0].text.decode()[1:-1]
        if not path.startswith("/"):
            continue
        method = prop.text.decode().upper()
        rows.append(
            {
                "endpoint": path,
                "methods": [method],
                "start_line": node.start_point.row + 1,
                "end_line": node.end_point.row + 1,
                "handler": args[-1].text.decode()[:120]
                if args[-1].type not in {"function_expression", "arrow_function"}
                else "inline handler",
                "route_quote": text.splitlines()[node.start_point.row].strip()[:300],
            }
        )
    return rows


def route_inventory(evidence, file, start=1, end=1000000):
    path = evidence.allowed(file)
    if path.stat().st_size > 200000 or path.suffix not in {".py", ".js", ".jsx"}:
        return {
            "routes": [],
            "limit": "No bounded route parser for this file; not proof of no routes",
        }
    text = path.read_text()
    rows = python_routes(text) if path.suffix == ".py" else javascript_routes(text)
    selected = [
        {
            **row,
            "file": file,
            "route_id": hashlib.sha256(
                f"{file}:{row['start_line']}:{row['endpoint']}".encode()
            ).hexdigest()[:16],
        }
        for row in rows
        if start <= row["start_line"] <= end
    ]
    return {
        "routes": selected[:40],
        "omitted": max(0, len(selected) - 40),
        "limit": "Syntactic registration only. Quotes are navigation, not citable evidence IDs. Verify bodies, middleware mounts, decorators and business permission contract using actual source. For each route separately inspect authentication, authorization and state transitions; do not bundle independent endpoints.",
    }


def condition_identity(evidence, row):
    location = row.primary_location.model_dump()
    routes = route_inventory(evidence, location["file"])["routes"]
    route = next(
        (r for r in routes if r["start_line"] <= location["line"] <= r["end_line"]),
        None,
    )
    operation = (
        route["start_line"]
        if route
        and row.security_property
        in {"authentication", "rate_limiting", "security_logging"}
        else location["line"]
    )
    return {
        "snapshot": evidence.audit.snapshot_hash,
        "file": location["file"],
        "operation_line": operation,
        "security_property": row.security_property,
    }
