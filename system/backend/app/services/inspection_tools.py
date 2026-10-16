"""Scoped read-only inspection pages with explicit requested/returned bounds."""

from app.domain.audit import AuditError
from app.services.context_materials import read_document

TOOL_CONTRACT = {
    "read_source": {
        "arguments": {
            "file": "relative source path",
            "start_line": "positive integer",
            "end_line": "inclusive integer",
        },
        "limit": "at most 151 complete lines and 12000 characters per returned page",
    },
    "read_document": {
        "arguments": {
            "file": "relative document path",
            "start_line": "positive integer",
            "end_line": "inclusive integer",
        },
        "limit": "same bounded read; omitted lines remain unread",
    },
    "search_source": {
        "arguments": {"text": "literal search string, at most 200 characters"},
        "limit": "no query or file parameter; navigation matches only",
    },
    "callers": {
        "arguments": {"symbol": "callable name"},
        "limit": "syntactic call clues, not resolved control flow",
    },
}


def read_page(evidence, name, arguments):
    if set(arguments) - {"file", "start_line", "end_line"}:
        raise AuditError("读取只接受file/start_line/end_line参数")
    file = arguments.get("file", "")
    start, requested_end = arguments.get("start_line", 1), arguments.get("end_line", 60)
    if (
        type(start) is not int
        or type(requested_end) is not int
        or start < 1
        or requested_end < start
    ):
        raise AuditError("源码读取起止行无效")
    path = evidence.allowed(file)
    if not path.is_file() or path.stat().st_size > 1024 * 1024:
        raise AuditError("源码取证文件超出读取范围")
    try:
        lines = path.read_text().splitlines()
    except UnicodeError as error:
        raise AuditError("取证文件不是UTF-8源码，保持未读状态") from error
    end = min(requested_end, start + 150, len(lines))
    while end >= start and len("\n".join(lines[start - 1 : end])) > 12000:
        end -= 1
    if end < start:
        raise AuditError("起始行不存在或单行过长；保留未读状态")
    operation = (
        evidence.read
        if name == "read_source"
        else lambda **args: read_document(evidence, **args)
    )
    row = operation(file=file, start_line=start, end_line=end)
    if end != requested_end:
        row = {
            **row,
            "read_adjustment": {
                "requested_end_line": requested_end,
                "returned_end_line": end,
                "total_lines": len(lines),
                "meaning": "Only the returned complete page was supplied; additional lines require a new read, EOF is explicit",
            },
        }
    return row
