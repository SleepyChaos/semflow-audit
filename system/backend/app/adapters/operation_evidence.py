"""Locate an exact supplied source quote; never infer an API from a nearby line."""

import hashlib

from app.adapters.source_inventory import inspectable
from app.domain.audit import AuditError


def normalize(text):
    return " ".join(text.split())


def locate_quote(row, context, language):
    file = row.primary_location.file
    quote = normalize(row.operation_quote)
    spans = set()
    supplied = set(map(str, row.evidence_ids))
    for material in context["evidence"]:
        ref = material["reference"]
        if (
            material["id"] not in supplied
            or material["kind"] != "code"
            or ref.get("file") != file
        ):
            continue
        if not inspectable(file, language):
            continue
        lines = material["content"].splitlines()
        for offset in range(len(lines)):
            # Short quotes may span up to four physical lines; all are supplied.
            for length in range(1, min(4, len(lines) - offset) + 1):
                text = normalize("\n".join(lines[offset : offset + length]))
                if quote in text:
                    spans.add((ref["start_line"] + offset, length))
                    break
    # Remove wider matches that start before the actual shortest match.
    locations = {
        start
        for start, length in spans
        if not any(other > start and other < start + length for other, _ in spans)
    }
    if not locations:
        raise AuditError("操作引用未出现于实际已提供源码", code="operation_unlocated")
    if len(locations) > 1:
        if row.primary_location.line not in locations:
            raise AuditError(
                "操作引用在多处出现，需提供独立且更明确的定位",
                code="operation_ambiguous",
            )
        line = row.primary_location.line
    else:
        line = next(iter(locations))
    original = row.primary_location.line
    row.primary_location.line = line
    return {
        "file": file,
        "line": line,
        "reported_line": original,
        "quote": row.operation_quote,
        "operation_id": hashlib.sha256(
            f"{context['snapshot']}:{file}:{line}:{quote}".encode()
        ).hexdigest()[:24],
        "meaning": "Exact quoted statement, not resolved runtime dispatch",
    }
