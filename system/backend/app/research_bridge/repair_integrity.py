"""Platform acceptance verifies research identity without legacy hash substitution."""

from uuid import uuid5

from semflow_contracts.repair import RepairResult
from semflow_research.public.repair_results import read_projection, verify_projection
from semflow_research.public.runs import inspect
from sqlmodel import Session, select

from app.adapters.artifacts import ArtifactStore
from app.core.db import engine
from app.domain.audit import AuditError
from app.persistence.stage_models import StageRun
from app.research_bridge.models import ResearchBinding
from app.research_bridge.protocol import verify_receipt
from app.research_bridge.repair_check_views import identity
from app.research_bridge.repair_inputs import platform_targets
from app.research_bridge.repair_projection import validation_view
from app.research_bridge.requests import research_root


def _verify_bound(record, audit):
    with Session(engine) as session:
        binding = session.exec(
            select(ResearchBinding).where(ResearchBinding.stage_id == record.stage_id)
        ).first()
        if binding is None:
            if record.validation.get("research_manifest"):
                raise AuditError("科研修复绑定丢失", code="integrity_error")
            return False
        envelope = inspect(binding.execution_id, root=research_root())
        if envelope is None:
            raise AuditError("科研修复没有已发布收据", code="integrity_error")
        envelope = verify_receipt(binding, audit, envelope)
        result = envelope.result
        if not isinstance(result, RepairResult):
            raise AuditError("科研修复没有类型化产物", code="integrity_error")
        manifest = envelope.manifest.model_dump(mode="json")
        expected_id = uuid5(
            record.stage_id, f"{binding.execution_id}/{result.repair_id}"
        )
        stage = session.get(StageRun, record.stage_id)
        targets = platform_targets(binding, result, stage.inputs["candidate_ids"])
        view = read_projection(result, root=research_root())
        # WIRE-RECV:research.repair_attempts — peer: repair_projection.validation_view.
        # AGENT: public artifact hashes and legacy native graph hashes are different
        # contracts. Verify original receipts and explicit ID mappings at both ends.
        if (
            record.id != expected_id
            or record.audit_id != audit.id
            or binding.entity_map.get(f"{binding.execution_id}/{result.repair_id}")
            != str(record.id)
            or binding.manifest != manifest
            or record.candidate_ids != targets
            or record.validation
            != validation_view(
                result,
                envelope,
                view,
                compatibility=identity(session, binding, stage, result)
                if binding.executor == "semflow-research/2"
                else None,
            )
        ):
            raise AuditError("修复投影身份或检查收据已变化", code="integrity_error")
        verify_projection(
            result,
            root=research_root(),
            target=ArtifactStore().directory(str(record.stage_id)),
            changes=record.changes,
        )

    return True


def verify_if_bound(record, audit):
    from semflow_contracts.errors import ResearchError

    try:
        return _verify_bound(record, audit)
    except ResearchError as exc:
        # Peer: repair API / comparison_state catch platform AuditError. Preserve
        # the research code/message while keeping exception families at the bridge.
        raise AuditError(str(exc), code=exc.code) from exc
