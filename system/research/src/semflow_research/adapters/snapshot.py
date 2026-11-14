"""Hash exactly the versioned source manifest, including retained documents."""

import hashlib
from pathlib import Path

from semflow_contracts.common import SourceFile, SourceManifest, digest

from semflow_research.domain.errors import AuditError


def snapshot_digest(root: Path) -> str:
    if not root.is_dir():
        raise AuditError("快照目录不存在", code="integrity_error")
    files = []
    for path in sorted(
        root.rglob("*"), key=lambda path: path.relative_to(root).as_posix()
    ):
        if path.is_symlink():
            raise AuditError("快照包含符号链接", code="integrity_error")
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
