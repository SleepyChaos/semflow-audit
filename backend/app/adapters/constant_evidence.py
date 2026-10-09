"""Bounded Astroid value clues for closed expressions, never a taint/safety oracle."""

import ast
from itertools import islice

import astroid
from astroid import nodes

ALLOWED = (
    nodes.Const,
    nodes.Name,
    nodes.BinOp,
    nodes.UnaryOp,
    nodes.Compare,
    nodes.BoolOp,
    nodes.Subscript,
    nodes.Slice,
    nodes.List,
    nodes.Tuple,
)


def closed(node, seen=None, depth=0):
    """Never infer a target call, attribute, imported name or mutable container."""
    seen = set() if seen is None else seen
    if depth > 8 or id(node) in seen or not isinstance(node, ALLOWED):
        return False
    seen = seen | {id(node)}
    if isinstance(node, nodes.Const):
        return (
            isinstance(node.value, (str, int, float, bool, type(None)))
            and len(repr(node.value)) <= 256
        )
    if isinstance(node, nodes.BinOp) and node.op in {"**", "<<", ">>"}:
        # Sequence multiplication and huge arithmetic can exhaust host memory.
        return False
    if (
        isinstance(node, nodes.BinOp)
        and node.op == "*"
        and not all(
            isinstance(child, nodes.Const)
            and isinstance(child.value, (int, float))
            and abs(child.value) <= 1000000
            for child in (node.left, node.right)
        )
    ):
        return False
    if isinstance(node, nodes.Name):
        _, definitions = node.lookup(node.name)
        if len(definitions) != 1 or not isinstance(definitions[0], nodes.AssignName):
            return False
        parent = definitions[0].parent
        if not isinstance(parent, nodes.Assign):
            return False
        if isinstance(parent.value, (nodes.List, nodes.Tuple)):
            return False  # Mutation/alias modeling is deliberately out of scope.
        return closed(parent.value, seen, depth + 1)
    return all(closed(child, seen, depth + 1) for child in node.get_children())


def literal_clues(body, *, limit=8):
    """Compare/selector results require real-source verification and branch reasoning."""
    if len(body.encode()) > 16000:
        return []
    try:
        tree = astroid.parse(body, apply_transforms=False)
        source_ast = ast.parse(body)
    except astroid.AstroidError, SyntaxError, ValueError:
        return []
    expressions = {}
    for original in ast.walk(source_ast):
        if isinstance(original, ast.expr):
            # A subscript and its receiver share coordinates; retain the outer expression.
            expressions.setdefault((original.lineno, original.col_offset), original)
    clues = []
    considered = 0
    for node in tree.nodes_of_class((nodes.Compare, nodes.Subscript, nodes.BinOp)):
        if considered >= 24 or len(clues) >= limit:
            break
        considered += 1
        # Avoid redundant arithmetic inside a comparison whose result is already shown.
        if isinstance(node.parent, (nodes.Compare, nodes.BinOp)) or not closed(node):
            continue
        try:
            inferred = list(islice(node.infer(), 3))
        except astroid.AstroidError, RecursionError, ValueError, TypeError:
            continue
        if (
            not inferred
            or len(inferred) >= 3
            or not all(isinstance(n, nodes.Const) for n in inferred)
        ):
            continue
        values = list(dict.fromkeys(repr(n.value) for n in inferred))
        if any(len(value) > 256 for value in values):
            continue
        original = expressions.get((node.lineno, node.col_offset))
        quote = ast.get_source_segment(body, original) if original else None
        if not quote or len(quote) > 300:
            continue
        clues.append(
            {"line": node.lineno, "quote": quote, "possible_literal_values": values}
        )
    return clues


def evidence_clues(materials):
    result = []
    for row in materials:
        if row["kind"] != "code" or not row["reference"].get("file", "").endswith(
            ".py"
        ):
            continue
        # Partial pages may not parse. They remain source evidence, not fabricated facts.
        for clue in literal_clues(row["content"]):
            result.append(
                {
                    **clue,
                    "line": clue["line"] + row["reference"].get("start_line", 1) - 1,
                    "file": row["reference"]["file"],
                    "evidence_id": row["id"],
                }
            )
    return result
