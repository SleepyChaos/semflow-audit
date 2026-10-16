"""Small read-only tool dispatcher shared by discovery and review."""

from app.domain.audit import AuditError
from app.services.inspection_progress import existing_read


def source_tool(evidence, call: dict) -> dict:
    name, arguments = call["name"], call["arguments"]
    if name == "read_source":
        return evidence.read(**arguments)
    if name == "search_source":
        return evidence.search(**arguments)
    if name == "callers":
        return evidence.callers(**arguments)
    raise AuditError("粗筛只允许源码读取、搜索和调用线索工具")


def grounded(rows: list[dict], location: dict) -> bool:
    return any(
        row["kind"] == "code"
        and row["reference"].get("file") == location["file"]
        and row["reference"]["start_line"]
        <= location["line"]
        <= row["reference"]["end_line"]
        for row in rows
    )


def window_observations(evidence, rows):
    result = []
    for row in rows:
        if row["kind"] != "code":
            continue
        reference = row["reference"]
        total = len(evidence.allowed(reference["file"]).read_text().splitlines())
        result.append(
            {
                "evidence_id": row["id"],
                **reference,
                "total_lines": total,
                "complete_file": reference["start_line"] == 1
                and reference["end_line"] == total,
            }
        )
    return result


def reused_read(context, call):
    traces = [
        {
            "name": r["tool"],
            "arguments": r["arguments"],
            "evidence_id": r["evidence_id"],
        }
        for r in context.get("tool_trace", [])
    ]
    return existing_read(
        call,
        context["evidence"],
        traces,
        file_lengths={
            row["file"]: row["total_lines"] for row in context.get("source_windows", [])
        },
    )


def observe_tool(context, call, data, reused=False):
    trace = {
        "tool": call["name"],
        "arguments": call["arguments"],
        "evidence_id": data["id"],
        "reused": reused,
    }
    count = sum(r.get("reused", False) for r in context.get("tool_trace", [])) + int(
        reused
    )
    if count > 2:
        raise AuditError("重复读取纠正次数耗尽，保留未决状态", code="no_progress")
    return {
        **context,
        "tool_trace": [*context.get("tool_trace", []), trace],
        "latest_tool_observation": {
            **trace,
            "meaning": "Read body is in evidence under this ID; requested window was already supplied"
            if reused
            else "Tool completed; actual returned body is in evidence under this ID",
        },
        "server_feedback": "Source evidence has been read by the host and contains actual bodies. Cite its supplied IDs. Do not request the same window again. Use source_windows to determine EOF. Return final when sufficient; otherwise request a NEW missing fact. Unknown premises remain insufficient, never exclusion.",
    }


def project_documents(evidence):
    rows = []
    for name in ("README.md", "pyproject.toml", "package.json"):
        if not (evidence.root / name).is_file():
            continue
        try:
            row = evidence.read(name, 1, 40)
        except AuditError:
            continue  # Selected path scope may exclude root documents.
        if len(row["content"]) <= 6000:
            rows.append(row)
        if len(rows) == 2:
            break
    return rows
