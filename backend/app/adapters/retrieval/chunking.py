"""Keep markdown sections and fenced API examples intact."""

from app.domain.audit import AuditError


def semantic_chunks(content: str, limit: int = 8000) -> list[str]:
    blocks, current, fenced = [], [], False
    for line in content.splitlines(keepends=True):
        if line.lstrip().startswith("```"):
            fenced = not fenced
        if not fenced and line.startswith("#") and current:
            blocks.append("".join(current))
            current = []
        current.append(line)
    if fenced:
        raise AuditError("知识代码块未闭合")
    if current:
        blocks.append("".join(current))
    chunks = []
    for block in blocks:
        if len(block) <= limit:
            chunks.append(block)
        elif "```" in block:
            raise AuditError("完整API/代码段过大，请按完整示例拆分文档")
        else:
            chunks.extend(
                block[start : start + limit] for start in range(0, len(block), limit)
            )
    return chunks


def source_chunks(content: str, limit: int = 8000) -> list[str]:
    """Exact nonoverlapping source windows. These are reference slices, not full rules."""
    chunks, lines, size = [], [], 0
    for line in content.splitlines(keepends=True):
        if len(line) > limit:
            raise AuditError("源码单行超过知识窗口预算")
        if size + len(line) > limit and lines:
            chunks.append("".join(lines))
            lines, size = [], 0
        lines.append(line)
        size += len(line)
    if lines:
        chunks.append("".join(lines))
    return chunks
