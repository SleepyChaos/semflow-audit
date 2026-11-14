"""Algorithm extracted from app.services.rule_drafts.

Runtime dependencies are passed explicitly; no platform ORM or configuration.
Changes to JSON require checking the corresponding semflow_contracts/wire peer.
"""

"""Durable candidate diagnostics, including failures before pack creation."""
import hashlib
import json
from uuid import UUID

from semflow_research.adapters.artifacts import ArtifactStore
from semflow_research.adapters.snapshot import snapshot_digest
from semflow_research.domain.errors import AuditError
from semflow_research.state.models import Evidence


def confirmed_evidence(candidate, audit, *, _kernel):
    evidence = []
    with _kernel.records.transaction() as db:
        for identifier in candidate.evidence_ids:
            row = db.get(Evidence, UUID(identifier))
            if (
                row is None
                or row.snapshot_id != audit.id
                or row.snapshot_hash != audit.snapshot_hash
            ):
                raise AuditError("已确认缺陷的规则证据缺失、跨任务或快照不匹配")
            if hashlib.sha256(row.content.encode()).hexdigest() != row.digest:
                raise AuditError("已确认缺陷的证据内容摘要不匹配")
            evidence.append(
                {
                    "id": str(row.id),
                    "kind": row.kind,
                    "reference": row.reference,
                    "content": row.content,
                    "digest": row.digest,
                }
            )
    if not evidence:
        raise AuditError("规则提炼需要已确认缺陷的实际证据")
    if (
        snapshot_digest(ArtifactStore(_kernel=_kernel).source(str(audit.snapshot_id)))
        != audit.snapshot_hash
    ):
        raise AuditError("规则提炼源代码快照已变化")
    return evidence


def save_candidate(directory, attempt, response):
    draft = directory / f"draft-{attempt}"
    draft.mkdir(parents=True, exist_ok=True)
    (draft / "candidate.json").write_text(
        json.dumps(response.model_dump(mode="json"), ensure_ascii=False, indent=2)
    )
    return draft


def save_diagnostic(pack, exc, log):
    feedback = {
        "message": str(exc),
        "code": "compiler_error" if "CodeQL" in str(exc) else "contract_error",
        "log_tail": log.read_text()[-8000:] if log.exists() else "",
    }
    (pack / "diagnostic.json").write_text(
        json.dumps(feedback, ensure_ascii=False, indent=2)
    )
    return feedback
