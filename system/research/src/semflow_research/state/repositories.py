"""Named scientific lifecycle repositories over an explicitly scoped record store."""

from uuid import UUID

from semflow_research.domain.errors import AuditError, ExecutionCancelled
from semflow_research.state.models import (
    ExecutionRecord,
    SourceRecord,
    get_datetime_utc,
)


class ExecutionRecords:
    def __init__(self, context):
        self.context = context

    def get(self, identifier):
        value = self.context.records.get(ExecutionRecord, identifier)
        if value is None:
            raise AuditError("科研执行不存在", code="identity_error")
        return value

    def active(self, identifier):
        if UUID(str(identifier)) == self.context.execution_id:
            self.context.control.check_active(self.context.execution_id)
        if self.get(identifier).status == "cancelled":
            raise ExecutionCancelled("科研执行已取消")

    def update(self, identifier, **values):
        # Interface peer: adapters.ai.provider.persist / generate call receipts.
        # AGENT: model_calls.method_version is the algorithm revision, while
        # prompt_version is the frozen template revision; never infer one from the other.
        # Telemetry records a call that already happened, including cancellation.
        # It must remain durable even when control disallows another model call.
        if not set(values).issubset({"usage", "model_calls", "model"}):
            self.active(identifier)
        with self.context.records.transaction() as records:
            value = self.get(identifier)
            for key, item in values.items():
                setattr(value, key, item)
            value.updated_at = get_datetime_utc()
            records.save(value)

    def claim(self, identifier):
        with self.context.records.transaction() as records:
            value = self.get(identifier)
            if value.status != "queued":
                return False
            value.status = "running"
            records.save(value)
            return True


class SourceRecords:
    def __init__(self, context):
        self.context = context

    def get(self, identifier):
        value = self.context.records.get(SourceRecord, identifier)
        if value is None or value.id != self.context.spec.source.snapshot_id:
            raise AuditError("源码快照不属于当前科研执行", code="identity_error")
        return value

    def update(self, identifier, **values):
        with self.context.records.transaction() as records:
            value = self.get(identifier)
            for key, item in values.items():
                setattr(value, key, item)
            records.save(value)
