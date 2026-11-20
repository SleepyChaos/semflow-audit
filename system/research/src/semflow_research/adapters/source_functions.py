"""Pure syntactic function ranges and risk hints for bounded source selection."""

import ast
from collections import Counter, defaultdict, deque

# Hints only. An API spelling does not prove reachability, binding, or a flaw.
_CALLS = {
    "process": (
        8,
        {
            "subprocess.run",
            "subprocess.call",
            "subprocess.Popen",
            "subprocess.check_output",
            "os.system",
            "os.popen",
        },
    ),
    "dynamic_execution": (8, {"eval", "exec", "compile"}),
    "deserialization": (
        7,
        {"pickle.load", "pickle.loads", "marshal.loads", "yaml.load"},
    ),
    "query_or_template": (
        6,
        {"execute", "executemany", "executescript", "render_template_string"},
    ),
    "io_boundary": (
        5,
        {
            "open",
            "send_file",
            "send_from_directory",
            "extractall",
            "urlopen",
            "requests.get",
            "requests.post",
        },
    ),
}
_LOOKUP = {
    name: (kind, weight) for kind, (weight, names) in _CALLS.items() for name in names
}


def dotted(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = dotted(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return ""


def declaration_span(node):
    """Keep the declaration and its decorators in the same source range."""
    return (
        min((item.lineno for item in node.decorator_list), default=node.lineno),
        node.end_lineno or node.lineno,
    )


class FunctionIndex(ast.NodeVisitor):
    def __init__(self, tree):
        self.scope = []
        self.current = None
        self.functions = []
        self.operations = []
        self.imports = {
            alias.asname or alias.name.split(".")[0]: (
                alias.name if alias.asname else alias.name.split(".")[0]
            )
            if isinstance(node, ast.Import)
            else f"{node.module}.{alias.name}"
            for node in tree.body
            if isinstance(node, ast.Import)
            or (isinstance(node, ast.ImportFrom) and node.module and not node.level)
            for alias in node.names
        }

    def visit_ClassDef(self, node):
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_FunctionDef(self, node):
        self.scope.append(node.name)
        outer = self.current
        start, end = declaration_span(node)
        row = {
            "name": node.name,
            "qualified_name": ".".join(self.scope),
            "start_line": start,
            "end_line": end,
            "locally_called": [],
            "call_hints": [],
        }
        self.functions.append(row)
        self.current = row
        self.generic_visit(node)
        self.current = outer
        self.scope.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Call(self, node):
        raw = dotted(node.func)
        first, separator, rest = raw.partition(".")
        qualified = self.imports.get(first, first) + separator + rest
        known = _LOOKUP.get(qualified) or (
            _LOOKUP.get(node.func.attr)
            if isinstance(node.func, ast.Attribute)
            else None
        )
        if known:
            kind, weight = known
            self.operations.append((node.lineno, kind, weight))
        if self.current is not None and isinstance(node.func, ast.Name):
            self.current["call_hints"].append((node.lineno, raw))
        self.generic_visit(node)


def index_source(tree):
    index = FunctionIndex(tree)
    index.visit(tree)
    names = Counter(row["name"] for row in index.functions)
    direct = defaultdict(set)
    for row in index.functions:
        for _, name in row["call_hints"]:
            if names[name] == 1:
                direct[name].add(row["qualified_name"])
    for row in index.functions:
        calls = row.pop("call_hints")
        row["locally_called"] = (
            sorted(direct[row["name"]])[:20] if names[row["name"]] == 1 else []
        )
        if row["locally_called"] and any(
            row["start_line"] <= line <= row["end_line"]
            for line, _, _ in index.operations
        ):
            index.operations.append((row["start_line"], "local_callers", 2))
        elif calls and any(names[name] == 1 for _, name in calls):
            index.operations.append((row["start_line"], "local_call_context", 1))
    return index.functions, index.operations


def prioritize_windows(units, operations):
    ranked = []
    for unit in units:
        signals = defaultdict(int)
        for line, reason, weight in operations.get(unit["file"], ()):
            if unit["start_line"] <= line <= unit["end_line"]:
                signals[reason] = max(signals[reason], weight)
        score = sum(signals.values())
        if score:
            unit["risk"] = {"score": score, "reasons": sorted(signals)}
            ranked.append(unit)
    ranked.sort(key=lambda u: -u["risk"]["score"])
    diverse, repeated = [], []
    seen = set()
    for unit in ranked:
        (repeated if unit["file"] in seen else diverse).append(unit)
        seen.add(unit["file"])
    risk, breadth = deque(diverse + repeated), deque(units)
    order, emitted = [], set()

    def take(queue, reason):
        while queue and queue[0]["id"] in emitted:
            queue.popleft()
        if queue:
            unit = queue.popleft()
            unit["selection_reason"] = reason
            order.append(unit)
            emitted.add(unit["id"])

    while risk and breadth:
        for _ in range(3):
            take(risk, "syntactic_risk")
        take(breadth, "breadth")
    while breadth:
        take(breadth, "breadth")
    return order
