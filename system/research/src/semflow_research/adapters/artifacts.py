"""Private algorithm working paths, separate from immutable public artifacts.

Paths never encode platform audit/stage IDs. Source and baseline are explicit
context resources; callers cannot infer a platform record from a directory UUID.
"""

from uuid import UUID

from semflow_research.domain.errors import AuditError


class ArtifactStore:
    def __init__(self, *, _kernel):
        self.context = _kernel

    def directory(self, identifier):
        identifier = UUID(str(identifier))
        if identifier == self.context.spec.source.snapshot_id:
            return self.context.baseline_directory
        if identifier not in self.context.records.scope:
            raise AuditError("工作产物不属于当前执行或显式上游", code="identity_error")
        if (
            identifier != self.context.execution_id
            and not self.context.records.read_upstream
        ):
            raise AuditError(
                "上游输入只允许读取冻结产物引用，不能读取可变工作目录",
                code="identity_error",
            )
        path = self.context.root / "workspaces" / str(identifier)
        if path.is_symlink():
            raise AuditError("工作目录不能为符号链接", code="integrity_error")
        path.mkdir(parents=True, exist_ok=True)
        return path

    def source(self, identifier):
        if UUID(str(identifier)) != self.context.spec.source.snapshot_id:
            raise AuditError("源码快照越界", code="identity_error")
        return self.context.source_root
