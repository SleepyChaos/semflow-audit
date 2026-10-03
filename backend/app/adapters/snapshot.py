"""Canonical hash of retained snapshot files, never a stage ID masquerading as a hash."""

import hashlib
from pathlib import Path

from app.domain.audit import AuditError


def snapshot_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise AuditError("快照包含不允许的符号链接")
        if path.is_file():
            digest.update(
                path.relative_to(root).as_posix().encode()
                + b"\0"
                + hashlib.sha256(path.read_bytes()).digest()
            )
    return digest.hexdigest()
