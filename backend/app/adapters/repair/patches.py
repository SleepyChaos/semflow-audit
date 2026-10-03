"""Apply exact replacements only in an isolated copy; original snapshots stay untouched."""

import difflib
import shutil
from pathlib import Path

from app.contracts.stages import ProposedChange
from app.domain.audit import AuditError

BLOCKED = {".env", ".git", "node_modules", ".venv"}
LOCKFILES = {"package-lock.json", "uv.lock", "poetry.lock", "bun.lock"}


def safe_file(root: Path, name: str) -> Path:
    if not name or "\\" in name or ":" in name or Path(name).is_absolute():
        raise AuditError("补丁文件路径无效")
    path = root / name
    if any(
        part in BLOCKED or part.startswith(".env")
        for part in path.relative_to(root).parts
    ):
        raise AuditError("补丁不能修改凭据或工作目录")
    resolved = path.resolve()
    if not resolved.is_relative_to(root.resolve()) or path.is_symlink():
        raise AuditError("补丁路径超出隔离工作区")
    if resolved.name in LOCKFILES or any(
        part in {"tests", "test", "__tests__"} for part in Path(name).parts
    ):
        raise AuditError("修复不能通过改动测试或锁文件绕过验证")
    return resolved


def apply_changes(
    source: Path,
    destination: Path,
    changes: list[ProposedChange],
    allowed_paths: list[str],
) -> str:
    if destination.exists():
        raise AuditError("隔离修复目录已存在；请创建新的修复执行")
    prepared = {}
    for change in changes:
        path = safe_file(source, change.file)
        relative = path.relative_to(source.resolve()).as_posix()
        if relative not in allowed_paths:
            raise AuditError("关联文件改动超出已批准修复范围")
        if not path.is_file() or path.stat().st_size > 1024 * 1024:
            raise AuditError("补丁目标不存在或过大")
        original, current = prepared.get(relative, (path.read_text(), path.read_text()))
        if current.count(change.old_text) != 1:
            raise AuditError("补丁旧文本必须在当前文件中精确匹配一次")
        updated = current.replace(change.old_text, change.new_text, 1)
        if updated == current:
            raise AuditError("补丁未改变任何源码")
        prepared[relative] = original, updated
    shutil.copytree(source, destination, symlinks=False)
    diffs = []
    for name, (original, updated) in prepared.items():
        target = destination / name
        target.write_text(updated)
        diffs.extend(
            difflib.unified_diff(
                original.splitlines(keepends=True),
                updated.splitlines(keepends=True),
                fromfile=f"a/{name}",
                tofile=f"b/{name}",
            )
        )
    patch = "".join(diffs)
    if not patch:
        raise AuditError("补丁没有生成 Diff")
    return patch
