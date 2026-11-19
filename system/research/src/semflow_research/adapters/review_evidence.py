"""Algorithm extracted from app.adapters.review_evidence.

Runtime dependencies are passed explicitly; no platform ORM or configuration.
Changes to JSON require checking the corresponding semflow_contracts/wire peer.
"""

"""Resolve named local proof gaps and reuse only verified, stage-local source pages."""
import hashlib
import re
from uuid import UUID

from semflow_research.domain.errors import AuditError

from semflow_research.adapters.source_text import read_source_text
from semflow_research.state.models import Evidence

SOURCE_PATH = re.compile(
    "(?<![A-Za-z0-9_./-])(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\\.(?:py|js|ts|jsx|tsx|json|yaml|yml|toml|ini|cfg|md|txt|html|htm|ejs|vue|svelte|graphql|gql)(?![A-Za-z0-9_./-])"
)


def missing_source_paths(assessment):
    text = "\n".join(
        [
            *assessment.get("missing_premises", []),
            *[
                p["reason"]
                for p in assessment.get("premises", [])
                if p["status"] == "missing"
            ],
        ]
    )
    return list(dict.fromkeys(SOURCE_PATH.findall(text)))


def retained_pages(evidence, file, *, _kernel):
    """A DB record alone cannot establish that its body still matches this snapshot."""
    path = evidence.allowed(file)
    lines = read_source_text(path).splitlines()
    with _kernel.records.transaction() as db:
        rows = db.list(
            Evidence,
            snapshot_id=evidence.source_context.id,
            execution_id=UUID(str(evidence.execution_id)),
            snapshot_hash=evidence.source_context.snapshot_hash,
            kind="code",
        )
    result = []
    for row in rows:
        if row.reference.get("file") != file:
            continue
        start, end = (
            row.reference.get("start_line", 0),
            row.reference.get("end_line", 0),
        )
        if (
            type(start) is not int
            or type(end) is not int
            or (not 1 <= start <= end <= len(lines))
            or (hashlib.sha256(row.content.encode()).hexdigest() != row.digest)
            or ("\n".join(lines[start - 1 : end]) != row.content)
        ):
            raise AuditError("补证缓存与不可变源码不一致", code="integrity_error")
        result.append(
            {
                "id": str(row.id),
                "kind": row.kind,
                "reference": row.reference,
                "content": row.content,
                "digest": row.digest,
            }
        )
    return sorted(
        result,
        key=lambda p: (
            p["reference"]["start_line"],
            -p["reference"]["end_line"],
            p["id"],
        ),
    )


def source_pages(evidence, file, current, *, _kernel):
    """Yield retained pages first, then uncovered legal windows; caller bounds consumption."""
    path = evidence.allowed(file)
    if not path.is_file() or path.stat().st_size > 1024 * 1024:
        raise AuditError("补证目标不是可读取的小型源码")
    total = len(read_source_text(path).splitlines())
    covered = set()
    for page in current:
        ref = page["reference"]
        if page["kind"] == "code" and ref.get("file") == file:
            covered.update(range(ref["start_line"], ref["end_line"] + 1))
    for page in retained_pages(evidence, file, _kernel=_kernel):
        ref = page["reference"]
        numbers = set(range(ref["start_line"], ref["end_line"] + 1))
        if numbers - covered:
            covered |= numbers
            yield (page, "retained_stage_evidence")
    start = 1
    while start <= total:
        if start in covered:
            start += 1
            continue
        end = start
        while end < min(total, start + 150) and end + 1 not in covered:
            end += 1
        page = evidence.read(file, start, end)
        covered.update(range(start, end + 1))
        yield (page, "targeted_source_read")
        start = end + 1
