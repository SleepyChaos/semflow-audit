"""Small, fail-closed Python checks of source-backed behavior claims."""

import ast
from dataclasses import dataclass
from pathlib import PurePosixPath

from semflow_research.adapters.source_text import read_source_text

from semflow_research.adapters.operation_evidence import normalize
from semflow_research.domain.errors import AuditError


@dataclass(frozen=True)
class BehaviorWitness:
    effect: str = "unverified"
    direct_flow: bool = False
    refs: tuple[str, ...] = ()
    detail: str = "The observed syntax alone does not establish the claimed effect."
    target_path: str | None = None
    supported_roles: tuple[str, ...] = ()


def inspect_behavior(
    evidence,
    location: dict,
    pages: list[dict],
    quote: str,
    property_name: str,
    weakness: str,
) -> BehaviorWitness:
    file, line = location["file"], location["line"]
    module = _parse(evidence, file)
    if module is None or not quote:
        return BehaviorWitness()
    source, tree = module
    scope = _enclosing(tree, line)
    if _direct_html(tree, scope, source, line, quote, property_name, weakness):
        refs = _covering(pages, file, scope.lineno, scope.end_lineno)
        wrapper = _route_declarations(tree, scope)
        globals_refs = tuple(
            ref
            for node in wrapper
            for ref in _covering(pages, file, node.lineno, node.end_lineno)
        )
        if (
            refs
            and wrapper
            and all(
                _covering(pages, file, node.lineno, node.end_lineno) for node in wrapper
            )
        ):
            decorator_refs = _covering(
                pages, file, scope.decorator_list[0].lineno, scope.lineno
            )
            if decorator_refs:
                return BehaviorWitness(
                    "supported",
                    True,
                    tuple(dict.fromkeys((*refs, *globals_refs, *decorator_refs))),
                    "Within the cited Flask handler, a request value flows unescaped to a raw HTML response on a straight-line path.",
                )
        if refs:
            return BehaviorWitness(
                effect="supported",
                refs=refs,
                target_path=file,
                detail="The cited handler body propagates the parsed value to its string return. Route and framework bindings still require cited source.",
                supported_roles=("propagation",),
            )
    # Limit a negative finding to the named operation and the exact cited body.
    hits = [
        n
        for n in ast.walk(scope or tree)
        if isinstance(n, ast.Call)
        and n.lineno <= line <= n.end_lineno
        and normalize(ast.get_source_segment(source, n) or "") == normalize(quote)
    ]
    if len(hits) != 1:
        return BehaviorWitness()
    call = hits[0]
    caller_refs = _covering(pages, file, call.lineno, call.end_lineno)
    if not caller_refs:
        return BehaviorWitness()
    resolved = _resolve_local(evidence, file, tree, scope, call)
    if resolved is None:
        return BehaviorWitness()
    callee_file, node, declaration = resolved
    bindings = [_covering(pages, file, line, line) for line in declaration.caller_lines]
    binding_refs = (
        tuple(dict.fromkeys(ref for group in bindings for ref in group))
        if all(bindings)
        else ()
    )
    callee_page_refs = _covering(pages, callee_file, declaration.line, node.end_lineno)
    if not callee_page_refs or not binding_refs:
        return BehaviorWitness(target_path=callee_file)
    if _empty(node):
        return BehaviorWitness(
            "refuted",
            False,
            tuple(dict.fromkeys((*caller_refs, *binding_refs, *callee_page_refs))),
            "The statically resolved local callable has only a no-op or literal return body.",
        )
    return BehaviorWitness(target_path=callee_file)


@dataclass(frozen=True)
class _Declaration:
    caller_lines: tuple[int, ...]
    line: int


def _enclosing(tree, line):
    return min(
        (
            n
            for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            and n.lineno <= line <= n.end_lineno
        ),
        key=lambda n: n.end_lineno - n.lineno,
        default=None,
    )


def _parse(evidence, file):
    if not file.endswith(".py"):
        return None
    try:
        p = evidence.allowed(file)
        if not p.is_file() or p.stat().st_size > 200000:
            return None
        text = read_source_text(p)
        return text, ast.parse(text)
    except (OSError, UnicodeError, SyntaxError, ValueError, RecursionError):
        return None
    except AuditError as exc:
        if exc.code in {"identity_error", "integrity_error"}:
            raise
        return None


def _covering(pages, path, first, last):
    return tuple(
        p["id"]
        for p in pages
        if p["kind"] == "code"
        and p["reference"].get("file") == path
        and p["reference"]["start_line"] <= first <= last <= p["reference"]["end_line"]
    )


def _assigns(node, name):
    return any(
        isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store) and n.id == name
        for n in ast.walk(node)
    )


def _resolve_local(evidence, file, tree, scope, call):
    fn = call.func
    member = fn.attr if isinstance(fn, ast.Attribute) else None
    base = fn.value if member else fn
    if not isinstance(base, ast.Name):
        return None
    name = base.id
    receiver = (
        _instance_binding(scope, name, member, call.lineno)
        if member and scope
        else None
    )
    if receiver:
        name = receiver.value.func.id
    if scope and (
        any(a.arg == name for a in ast.walk(scope.args) if isinstance(a, ast.arg))
        or _assigns(scope, name)
    ):
        return None
    if any(_assigns(n, name) for n in tree.body):
        return None
    if member and any(
        isinstance(n, ast.Attribute)
        and isinstance(n.ctx, ast.Store)
        and isinstance(n.value, ast.Name)
        and n.value.id == name
        and n.attr == member
        for n in ast.walk(tree)
    ):
        return None
    decls = [
        (node, name)
        for node in tree.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == name
    ]
    decls.extend(
        (node, item.name)
        for node in tree.body
        if isinstance(node, ast.ImportFrom)
        for item in node.names
        if (item.asname or item.name) == name
    )
    # Refuse ambiguous definitions and module-level dynamic import guessing.
    if len(decls) != 1 or _ambiguous_imports(tree, name, decls[0][0]):
        return None
    declaration, symbol = decls[0]
    path, node = file, declaration
    if isinstance(declaration, ast.ImportFrom):
        if not declaration.module or declaration.level > 1:
            return None
        stem = declaration.module.replace(".", "/")
        parent = PurePosixPath(file).parent
        bases = (
            [parent / stem]
            if declaration.level
            else list(dict.fromkeys((parent / stem, PurePosixPath(stem))))
        )
        options = list(
            dict.fromkeys(
                str(p) for b in bases for p in (b.with_suffix(".py"), b / "__init__.py")
            )
        )
        modules = [
            (path, m) for path in options if (m := _parse(evidence, path)) is not None
        ]
        if len(modules) != 1:
            return None
        path, (_, module) = modules[0]
        if any(_assigns(n, symbol) for n in module.body) or _ambiguous_imports(
            module, symbol
        ):
            return None
        choices = [
            n
            for n in module.body
            if isinstance(n, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
            and n.name == symbol
        ]
        if len(choices) != 1:
            return None
        node = choices[0]
    first = node.lineno
    if receiver and not _plain_instance(node, member):
        return None
    if member:
        if (
            not isinstance(node, ast.ClassDef)
            or node.bases
            or node.keywords
            or node.decorator_list
        ):
            return None
        choices = [
            n
            for n in node.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            and n.name == member
        ]
        if len(choices) != 1 or any(_assigns(n, member) for n in node.body):
            return None
        node = choices[0]
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return None
    if any(
        not isinstance(d, ast.Name) or d.id != "staticmethod"
        for d in node.decorator_list
    ):
        return None
    lines = (declaration.lineno, receiver.lineno) if receiver else (declaration.lineno,)
    return path, node, _Declaration(lines, first)


def _instance_binding(scope, name, member, before):
    assignments = [
        stmt
        for stmt in scope.body
        if isinstance(stmt, ast.Assign)
        and len(stmt.targets) == 1
        and isinstance(stmt.targets[0], ast.Name)
        and stmt.targets[0].id == name
        and stmt.end_lineno < before
        and isinstance(stmt.value, ast.Call)
        and isinstance(stmt.value.func, ast.Name)
    ]
    if len(assignments) != 1:
        return None
    references = {
        n
        for n in ast.walk(scope)
        if isinstance(n, ast.Name)
        and n.id == name
        and n.lineno < before
        and n is not assignments[0].targets[0]
    }
    bound_calls = {
        n.func.value
        for n in ast.walk(scope)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == member
    }
    if references - bound_calls:
        return None
    return assignments[0]


def _plain_instance(node, member):
    if not isinstance(node, ast.ClassDef):
        return False
    methods = [item for item in node.body if isinstance(item, ast.FunctionDef)]
    if any(
        item.name in {"__new__", "__getattribute__", "__getattr__", "__setattr__"}
        for item in methods
    ):
        return False
    constructors = [item for item in methods if item.name == "__init__"]
    if not constructors:
        return True
    if len(constructors) != 1:
        return False
    ctor = constructors[0]
    if ctor.decorator_list or not ctor.args.args:
        return False
    self = ctor.args.args[0].arg
    return all(
        isinstance(stmt, ast.Pass)
        or (
            isinstance(stmt, ast.Assign)
            and len(stmt.targets) == 1
            and isinstance(target := stmt.targets[0], ast.Attribute)
            and isinstance(target.value, ast.Name)
            and target.value.id == self
            and target.attr != member
            and isinstance(stmt.value, (ast.Name, ast.Constant))
        )
        for stmt in ctor.body
    )


def _ambiguous_imports(tree, name, expected=None):
    for node in ast.walk(tree):
        if node is expected:
            continue
        if isinstance(node, ast.ImportFrom) and any(
            (alias.asname or alias.name) in {"*", name} for alias in node.names
        ):
            return True
        if isinstance(node, ast.Import) and any(
            (alias.asname or alias.name.split(".")[0]) == name for alias in node.names
        ):
            return True
    return False


def _empty(node):
    return all(
        isinstance(n, ast.Pass)
        or isinstance(n, ast.Expr)
        and isinstance(n.value, ast.Constant)
        and isinstance(n.value.value, str)
        or isinstance(n, ast.Return)
        and (n.value is None or isinstance(n.value, ast.Constant))
        for n in node.body
    )


def _route_declarations(tree, scope):
    if not scope or len(scope.decorator_list) != 1:
        return ()
    decorator = scope.decorator_list[0]
    if not isinstance(decorator, ast.Call) or not isinstance(
        decorator.func, ast.Attribute
    ):
        return ()
    name = decorator.func.value
    if not isinstance(name, ast.Name) or decorator.func.attr not in {
        "route",
        "get",
        "post",
    }:
        return ()
    imports = [
        n
        for n in tree.body
        if isinstance(n, ast.ImportFrom)
        and n.module == "flask"
        and not n.level
        and any(i.name == "Flask" and not i.asname for i in n.names)
    ]
    requests = [
        n
        for n in tree.body
        if isinstance(n, ast.ImportFrom)
        and n.module == "flask"
        and not n.level
        and any(i.name == "request" and not i.asname for i in n.names)
    ]
    assignments = [n for n in tree.body if _assigns(n, name.id)]
    if (
        len(imports) != 1
        or len(requests) != 1
        or len(assignments) != 1
        or _assigns(tree, "request")
    ):
        return ()
    if (
        _assigns(tree, "Flask")
        or _ambiguous_imports(tree, "Flask", imports[0])
        or _ambiguous_imports(tree, "request", requests[0])
    ):
        return ()
    obj = assignments[0]
    if (
        not isinstance(obj, ast.Assign)
        or not isinstance(obj.value, ast.Call)
        or not isinstance(obj.value.func, ast.Name)
        or obj.value.func.id != "Flask"
        or obj.value.keywords
    ):
        return ()
    if any(
        isinstance(n, ast.Attribute)
        and isinstance(n.value, ast.Name)
        and n.value.id == name.id
        and n.attr in {"before_request", "after_request", "wsgi_app"}
        for n in ast.walk(tree)
    ):
        return ()
    return tuple(dict.fromkeys((*imports, *requests, obj)))


def _direct_html(tree, scope, source, line, quote, prop, cwe):
    if (
        prop != "output_encoding"
        or cwe != "CWE-79"
        or not scope
        or not _route_declarations(tree, scope)
    ):
        return False
    if not scope.body or any(
        a.arg == "request" for a in ast.walk(scope.args) if isinstance(a, ast.arg)
    ):
        return False
    assigned = {}

    def request_value(n):
        if isinstance(n, ast.Name):
            return assigned.get(n.id, False)
        return (
            isinstance(n, ast.Subscript)
            and isinstance(n.value, ast.Attribute)
            and n.value.attr in {"args", "form"}
            and isinstance(n.value.value, ast.Name)
            and n.value.value.id == "request"
            and isinstance(n.slice, ast.Constant)
            and isinstance(n.slice.value, str)
        )

    for stmt in scope.body[:-1]:
        if (
            not isinstance(stmt, ast.Assign)
            or len(stmt.targets) != 1
            or not isinstance(stmt.targets[0], ast.Name)
            or not request_value(stmt.value)
        ):
            return False
        assigned[stmt.targets[0].id] = True
    out = scope.body[-1]
    val = out.value if isinstance(out, ast.Return) else None
    if not isinstance(val, ast.JoinedStr) or not out.lineno <= line <= out.end_lineno:
        return False
    if normalize(ast.get_source_segment(source, out) or "") != normalize(quote):
        return False
    fields = [v for v in val.values if isinstance(v, ast.FormattedValue)]
    return bool(fields) and all(
        f.conversion == -1 and f.format_spec is None and request_value(f.value)
        for f in fields
    )
