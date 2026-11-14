"""Translate immutable technical comparison into the established platform DTO."""

from uuid import UUID, uuid5

from semflow_contracts.common import canonical_bytes
from semflow_contracts.runs import validate_spec
from semflow_research.public.comparisons import read
from sqlmodel import select

from app.adapters.artifacts import ArtifactStore
from app.domain.audit import AuditError
from app.models import get_datetime_utc
from app.persistence.audit_models import AuditRun
from app.persistence.stage_models import StageRun
from app.research_bridge.protocol import verify_receipt
from app.research_bridge.repair_projection import save_view
from app.services.context_materials import digest


def project(session, binding, envelope, *, root):
    stage = session.exec(
        select(StageRun).where(StageRun.id == binding.stage_id).with_for_update()
    ).one()
    envelope = verify_receipt(binding, session.get(AuditRun, stage.audit_id), envelope)
    manifest = envelope.manifest.model_dump(mode="json")
    if binding.manifest is not None and binding.manifest != manifest:
        raise AuditError("前后对比科研清单已变化", code="integrity_error")
    body = read(envelope, root=root)
    refs = validate_spec(binding.request).inputs.suite.target_refs
    ids = {}
    for reference in refs:
        mapped = binding.entity_map.get(
            f"{reference.execution_id}/{reference.entity_id}"
        )
        if (
            mapped is None
            or uuid5(reference.execution_id, "candidate/" + mapped)
            != reference.entity_id
        ):
            raise AuditError("比较输入的目标映射已变化", code="identity_mismatch")
        ids[str(reference.entity_id)] = mapped
    for case in body["cases"]:
        if any(i not in ids for i in case["candidate_ids"]):
            raise AuditError("前后对比目标映射缺失", code="identity_mismatch")
        case["candidate_ids"] = [ids[i] for i in case["candidate_ids"]]
    suite_stage = session.get(StageRun, UUID(stage.inputs["suite_id"]))
    from app.persistence.stage_models import RepairRecord

    record = session.get(RepairRecord, UUID(stage.inputs["repair_id"]))
    repair_stage = session.get(StageRun, record.stage_id)
    # WIRE-RECV:research.result — peer: runtime.repair_verify.verify.
    # AGENT: scientific identity is preserved separately from the legacy view;
    # conversion must never change assertions, technical status or human acceptance.
    result = {
        **{k: v for k, v in body.items() if k not in {"identity", "suite", "repair"}},
        "identity": stage.inputs["identity"],
        "research_identity": envelope.result.identity.model_dump(mode="json"),
        "research_receipt": {
            "execution_id": str(envelope.execution_id),
            "manifest": manifest,
        },
        "image_id": envelope.result.identity.image_digest,
        "suite_created_before_repair": suite_stage.created_at
        <= repair_stage.created_at,
        "suite_title": suite_stage.result["suite"]["title"],
        "test_origin": suite_stage.result["origin"],
        "assumptions": suite_stage.result["suite"].get("assumptions", []),
        "human_test_review_required": True,
    }
    result["receipt_hash"] = digest(result)
    save_view(
        ArtifactStore().directory(str(stage.id)) / "comparison.json",
        canonical_bytes(result),
    )
    if binding.manifest is None:
        if stage.status != "cancelled":
            stage.status = envelope.execution_status
        stage.result, stage.usage = result, envelope.usage.model_dump(mode="json")
        stage.phase, stage.updated_at = "verification_ready", get_datetime_utc()
        binding.manifest = manifest
        session.add(stage)
        session.add(binding)
        session.commit()
        session.refresh(stage)
    return stage
