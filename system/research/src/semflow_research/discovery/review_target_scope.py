"""Detect an operation quote attributed to a different Python handler."""

import ast

from semflow_research.adapters.operation_evidence import normalize
from semflow_research.domain.errors import AuditError


def guard_operation_scope(evidence, target: dict, assessment, cited) -> None:
    operation = next((p for p in assessment.premises if p.premise == "operation"), None)
    location = target["location"]
    file = location["file"]
    if (
        operation is None
        or operation.status not in {"established", "contradicted"}
        or not operation.quote
        or not file.endswith(".py")
    ):
        return
    rows = [
        row
        for row in cited(operation.evidence_ids)
        if row["kind"] == "code"
        and row["reference"].get("file") == file
        and normalize(operation.quote) in normalize(row["content"])
    ]
    if not rows:
        return
    try:
        path = evidence.allowed(file)
        if path.stat().st_size > 1024 * 1024:
            return
        body = path.read_text(encoding="utf-8-sig")
        tree = ast.parse(body)
    except (SyntaxError, ValueError, OSError, UnicodeError, RecursionError):
        return
    except AuditError as error:
        if error.code in {"integrity_error", "identity_error"}:
            raise
        return
    functions = [
        n
        for n in ast.walk(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    line = location["line"]
    targets = [n for n in functions if _start(n) <= line <= n.end_lineno]
    if not targets:
        return
    handler = min(targets, key=lambda node: node.end_lineno - _start(node))
    # Allow evidence from actual same-file helper candidates referenced by the
    # handler. Finding a textual name here does not establish an execution edge.
    direct = {
        n.id
        for call in ast.walk(handler)
        if isinstance(call, ast.Call) and isinstance(n := call.func, ast.Name)
    }
    lines = body.splitlines()
    quote = normalize(operation.quote)

    def contains(node):
        return any(
            quote
            in normalize(
                "\n".join(
                    lines[
                        max(_start(node), r["reference"]["start_line"]) - 1 : min(
                            node.end_lineno, r["reference"]["end_line"]
                        )
                    ]
                )
            )
            for r in rows
        )

    if (
        not contains(handler)
        and any(
            node is not handler and node.name not in direct and contains(node)
            for node in functions
        )
        and not any(contains(node) for node in functions if node.name in direct)
    ):
        raise AuditError(
            "操作引文落在另一个函数，和冻结候选位置不一致",
            code="candidate_scope_mismatch",
        )


def _start(node):
    return min((d.lineno for d in node.decorator_list), default=node.lineno)
