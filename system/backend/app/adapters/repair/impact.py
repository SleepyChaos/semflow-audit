"""Bounded syntactic caller obligations for changed Python functions."""

import ast
from collections import defaultdict


def changed_functions(original, candidate):
    def functions(text):
        tree = ast.parse(text)
        return {
            node.name: ast.dump(node, include_attributes=False)
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }

    before, after = functions(original), functions(candidate)
    return sorted(name for name, body in before.items() if after.get(name) != body)


def caller_obligations(evidence, changes, workspace, *, max_windows=8):
    """Lexical clues are explicit, not a claim of resolved Python dispatch."""
    changed = set()
    for name in {
        change["file"] for change in changes if change["file"].endswith(".py")
    }:
        try:
            changed.update(
                changed_functions(
                    evidence.allowed(name).read_text(), (workspace / name).read_text()
                )
            )
        except SyntaxError, UnicodeError:
            continue  # Actual syntax validator remains authoritative.
    if not changed:
        return {
            "obligations": [],
            "evidence": [],
            "limitations": [
                "No changed Python function inferred; module-level and dynamic effects require separate assessment"
            ],
        }
    reverse = defaultdict(list)
    for path in evidence.files():
        if path.suffix != ".py" or path.stat().st_size > 1024 * 1024:
            continue
        try:
            tree = ast.parse(path.read_text())
        except SyntaxError, UnicodeError:
            continue
        parents = {}
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                parents[child] = node
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            callee = (
                node.func.id
                if isinstance(node.func, ast.Name)
                else node.func.attr
                if isinstance(node.func, ast.Attribute)
                else None
            )
            if not callee:
                continue
            parent = parents.get(node)
            while parent is not None and not isinstance(
                parent, (ast.FunctionDef, ast.AsyncFunctionDef)
            ):
                parent = parents.get(parent)
            reverse[callee].append(
                {
                    "file": path.relative_to(evidence.root).as_posix(),
                    "line": node.lineno,
                    "caller": parent.name if parent else "<module>",
                    "callee": callee,
                }
            )
    selected, frontier, seen = [], changed, set()
    for depth in range(2):
        following = set()
        for name in sorted(frontier):
            for row in sorted(
                reverse[name], key=lambda row: (row["file"], row["line"])
            ):
                identity = (row["file"], row["line"], row["callee"])
                if identity in seen:
                    continue
                seen.add(identity)
                selected.append({**row, "distance_from_changed_function": depth + 1})
                following.add(row["caller"])
        frontier = following
    obligations, materials = [], []
    for row in selected[:max_windows]:
        material = evidence.read(row["file"], max(1, row["line"] - 8), row["line"] + 8)
        materials.append(material)
        obligations.append(
            {
                "id": len(obligations),
                **row,
                "evidence_id": material["id"],
                "requirement": "Explain whether this existing caller changes behavior outside the confirmed request. Preserve unrelated use, or return unknown/conflicting with actual source citations.",
            }
        )
    return {
        "changed_functions": sorted(changed),
        "obligations": obligations,
        "evidence": materials,
        "omitted_call_sites": max(0, len(selected) - max_windows),
        "limitations": [
            "Two-level syntactic name matching only; imports, aliases and dynamic dispatch are not resolved. Missing matches do not establish absence of callers."
        ],
    }
