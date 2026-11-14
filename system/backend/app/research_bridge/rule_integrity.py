"""Platform confirmation checks; research never queries these mutable decisions."""

from uuid import UUID

from semflow_contracts.common import digest
from sqlmodel import select

from app.adapters.artifacts import ArtifactStore
from app.domain.audit import AuditError
from app.persistence.audit_models import AuditRun
from app.persistence.stage_models import Candidate, Decision


def capture_confirmation(session, stage):
    identifier = stage.inputs.get("candidate_id")
    if not identifier:
        return None
    candidate = session.get(Candidate, UUID(identifier))
    latest = session.exec(
        select(Decision)
        .where(Decision.candidate_id == candidate.id)
        .order_by(Decision.created_at.desc(), Decision.id.desc())
    ).first()
    if (
        candidate.status != "confirmed"
        or latest is None
        or latest.status != "confirmed"
    ):
        raise AuditError("规则目标缺少最新人工确认", code="target_not_authorized")
    return {
        "candidate_id": identifier,
        "candidate_digest": digest(candidate.model_dump(mode="json")),
        "decision_id": str(latest.id),
        "decision_digest": digest(latest.model_dump(mode="json")),
    }


def verify_confirmation(session, stage):
    # Peer: rule_requests.freeze_rule / approve_stage / project_rule / publish.
    # AGENT: changed human input cannot renew an old scientific execution; source
    # evidence and latest decision stay bound to the originally frozen request.
    if "research_input_confirmation" not in stage.result:
        raise AuditError("规则缺少冻结的平台确认身份", code="integrity_error")
    audit = session.get(AuditRun, stage.audit_id)
    if stage.result.get("research_platform_baseline") != capture_baseline(audit):
        raise AuditError("原规则基线已变化", code="integrity_error")
    if (
        stage.result.get("research_platform_inputs_digest") != digest(stage.inputs)
        or capture_confirmation(session, stage)
        != stage.result["research_input_confirmation"]
    ):
        raise AuditError(
            "规则目标或人工确认已变化，请创建新执行", code="integrity_error"
        )


def capture_baseline(audit):
    from app.services.context_materials import digest as legacy_digest

    metadata = ArtifactStore().directory(str(audit.id)) / "database/codeql-database.yml"
    return {
        "snapshot": audit.snapshot_hash,
        "findings": legacy_digest(audit.findings),
        "cli": audit.codeql_version,
        "query_pack": audit.query_pack,
        "custom_rules": audit.custom_rule_ids,
        "metadata": legacy_digest(metadata.read_text()),
    }
