"""Project native receipts into platform identities, records and disposable views."""

from uuid import uuid5

from semflow_contracts.repair import RepairResult, RepairVerifyResult, SuiteBuildResult
from semflow_contracts.results import ResultEnvelope
from semflow_research.public.repair_results import materialize_projection
from sqlmodel import select

from app.adapters.artifacts import ArtifactStore
from app.domain.audit import AuditError
from app.models import get_datetime_utc
from app.persistence.audit_models import AuditRun
from app.persistence.stage_models import RepairRecord, StageRun
from app.research_bridge.protocol import verify_receipt
from app.research_bridge.repair_inputs import platform_targets


def save_view(path, content):
    if path.exists() and (path.is_symlink() or path.read_bytes() != content):
        raise AuditError("已有修复展示文件与不可变产物不同", code="integrity_error")
    if not path.exists():
        path.write_bytes(content)


def validation_view(result, envelope, projection, *, compatibility=None):
    # WIRE-RECV:research.repair_attempts — peer: public.repair_results.read_projection.
    # AGENT: named old DTO checks carry the original receipt. Missing execution is
    # not_run, never passed. Keep typed checks and public byte identities alongside.
    from app.research_bridge.repair_check_views import project

    named = (
        project(projection.checks, compatibility)
        if compatibility is not None
        else projection.checks
    )
    return {
        **named,
        "isolated_tests": named.get(
            "isolated_tests", {"status": "not_run", "reason": "本执行未选择项目测试"}
        ),
        "rescan": named.get(
            "rescan", {"status": "not_run", "reason": "本执行未选择重扫"}
        ),
        "outcome": result.outcome,
        "checks": [check.model_dump(mode="json") for check in result.checks],
        "attempts_ref": result.attempts.model_dump(mode="json"),
        "semantic_context": result.semantic_context.model_dump(mode="json"),
        "original_snapshot_unchanged": True,
        "research_manifest": envelope.manifest.model_dump(mode="json"),
        "summary": projection.proposal.get("summary", ""),
    }


def project_repair(session, binding, result, *, root):
    # WIRE-RECV:research.result — peer: execution.execute / repair_runtime.execute_bound.
    # AGENT: projection copies immutable bytes/statuses only; it never accepts a
    # patch or overwrites a human decision. Change sender and schema together.
    envelope = ResultEnvelope.model_validate_json(result.model_dump_json())
    if isinstance(envelope.result, SuiteBuildResult):
        from app.research_bridge.suite_projection import project

        return project(session, binding, envelope, root=root)
    if isinstance(envelope.result, RepairVerifyResult):
        from app.research_bridge.comparison_projection import project

        return project(session, binding, envelope, root=root)
    stage = session.exec(
        select(StageRun).where(StageRun.id == binding.stage_id).with_for_update()
    ).one()
    envelope = verify_receipt(binding, session.get(AuditRun, stage.audit_id), envelope)
    manifest = envelope.manifest.model_dump(mode="json")
    if binding.manifest is not None and binding.manifest != manifest:
        raise AuditError("修复结果清单已变化", code="integrity_error")
    already_projected = binding.manifest is not None
    receipt = {"execution_id": str(envelope.execution_id), "manifest": manifest}
    if envelope.result is None:
        if envelope.execution_status not in {"failed", "cancelled", "interrupted"}:
            raise AuditError("无修复产物的状态不合法", code="invalid_contract")
        projected = {
            "research_receipt": receipt,
            "failure": envelope.failure.model_dump(mode="json")
            if envelope.failure
            else None,
            "completeness": envelope.completeness.model_dump(mode="json"),
        }
    else:
        if not isinstance(envelope.result, RepairResult):
            raise AuditError("科研结果不是 RepairResult", code="identity_mismatch")
        result = envelope.result
        directory = ArtifactStore().directory(str(stage.id))
        directory.mkdir(parents=True, exist_ok=True)
        projection = materialize_projection(result, root=root, target=directory)
        if projection.patch_bytes is not None:
            save_view(directory / "repair.diff", projection.patch_bytes)
        save_view(directory / "repair-context.json", projection.context_bytes)
        key = f"{binding.execution_id}/{result.repair_id}"
        identifier = uuid5(stage.id, key)
        if key in binding.entity_map and binding.entity_map[key] != str(identifier):
            raise AuditError("修复身份映射已变化", code="identity_mismatch")
        targets = platform_targets(binding, result, stage.inputs["candidate_ids"])
        from app.research_bridge.repair_check_views import identity

        validation = validation_view(
            result,
            envelope,
            projection,
            compatibility=identity(session, binding, stage, result)
            if binding.executor == "semflow-research/2"
            else None,
        )
        record = session.get(RepairRecord, identifier)
        if record is None:
            if already_projected:
                raise AuditError("已提交的修复投影记录丢失", code="integrity_error")
            record = RepairRecord(
                id=identifier,
                stage_id=stage.id,
                audit_id=stage.audit_id,
                candidate_ids=targets,
                changes=projection.proposal.get("changes", []),
                validation=validation,
                status="checks_passed"
                if result.outcome == "checks_passed"
                else "needs_review",
            )
            session.add(record)
        elif (
            record.stage_id != stage.id
            or record.audit_id != stage.audit_id
            or record.candidate_ids != targets
            or record.changes != projection.proposal.get("changes", [])
            or record.validation != validation
        ):
            raise AuditError("已投影的修复内容不可替换", code="integrity_error")
        # Preserve acceptance status/actor/reason on redelivery.
        binding.entity_map = {**binding.entity_map, key: str(identifier)}
        projected = {
            "repair_id": str(record.id),
            "research_receipt": receipt,
            "validation": validation,
            "status": record.status,
            "summary": validation["summary"],
        }
    if not already_projected:
        # A platform cancellation racing a completed receipt remains a cancellation;
        # the scientific terminal status is retained in the immutable receipt.
        if stage.status != "cancelled":
            stage.status = envelope.execution_status
        stage.phase = (
            "cancelled"
            if stage.status == "cancelled"
            else "repair_result_ready"
            if envelope.result
            else "repair_failed"
        )
        stage.error = envelope.failure.message if envelope.failure else None
        stage.result = projected
        stage.usage = envelope.usage.model_dump(mode="json")
        stage.updated_at = get_datetime_utc()
        binding.manifest = manifest
        session.add(stage)
        session.add(binding)
        from app.persistence.stage_repository import record_followup

        record_followup(session, stage)
        session.commit()
        session.refresh(stage)
    return stage
