from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AuditPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    project_name: str
    language: str
    status: str
    phase: str
    snapshot_hash: str
    query_pack: str
    suite: str
    codeql_version: str | None
    error: str | None
    coverage: dict
    created_at: datetime
    updated_at: datetime
    findings: list[dict]
