from dataclasses import dataclass
from enum import StrEnum


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AuditError(Exception):
    """A stage failed; never interpret this as zero findings."""


class AuditCancelled(AuditError):
    """Execution stopped at a stage boundary after cancellation."""


@dataclass(frozen=True)
class ScanPlan:
    language: str
    query_pack: str
    suite: str
