"""Hash exactly the versioned source manifest, including retained documents."""

import hashlib
from pathlib import Path

from semflow_contracts.common import SourceFile, SourceManifest, digest

from semflow_research.domain.errors import AuditError


def is_link(path: Path) -> bool:
    return path.is_symlink() or path.is_junction()


def snapshot_digest(root: Path) -> str:
    if is_link(root):
        raise AuditError("快照根目录包含链接", code="integrity_error")
    if not root.is_dir():
        raise AuditError("快照目录不存在", code="integrity_error")
    files = []
    for path in sorted(
        root.rglob("*"), key=lambda path: path.relative_to(root).as_posix()
    ):
        if is_link(path):
            raise AuditError("快照包含符号链接或目录联接", code="integrity_error")
        if path.is_file():
            raw = path.read_bytes()
            files.append(
                SourceFile(
                    path=path.relative_to(root).as_posix(),
                    sha256=hashlib.sha256(raw).hexdigest(),
                    size_bytes=len(raw),
                )
            )
    return digest(SourceManifest(files=tuple(files)))
