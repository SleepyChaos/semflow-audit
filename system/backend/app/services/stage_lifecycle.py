"""Transport-independent stage creation and experiment input validation."""

from uuid import UUID

from sqlmodel import Session, select

from app.contracts.stage_execution import default_version, validate_inputs
from app.domain.audit import AuditError
from app.persistence.audit_models import AuditRun
from app.persistence.stage_models import Candidate, RepairRecord, StageRun


def owned_audit(session: Session, identifier: UUID, owner_id: UUID) -> AuditRun:
    identifier = UUID(str(identifier))
    run = session.get(AuditRun, identifier)
    if run is None or run.owner_id != owner_id:
        raise AuditError("审计任务不存在", code="not_found")
    return run


def owned_stage(session: Session, identifier: UUID, owner_id: UUID) -> StageRun:
    identifier = UUID(str(identifier))
    stage = session.get(StageRun, identifier)
    if stage is None:
        raise AuditError("阶段执行不存在", code="not_found")
    owned_audit(session, stage.audit_id, owner_id)
    return stage


def validate_targets(session: Session, audit: AuditRun, kind: str, inputs: dict):
    if kind == "repair":
        identifiers = {UUID(value) for value in inputs["candidate_ids"]}
        candidates = session.exec(
            select(Candidate).where(
                Candidate.audit_id == audit.id, Candidate.id.in_(identifiers)
            )
        ).all()
        if len(candidates) != len(identifiers) or any(
            row.status != "confirmed" for row in candidates
        ):
            raise AuditError("请选择本次审计中人工确认的缺陷")
        if inputs.get("verification_suite_id"):
            from app.services.verification_suites import read_suite, target_ids

            suite = read_suite(UUID(inputs["verification_suite_id"]), audit.id)[1]
            if not set(map(str, identifiers)).issubset(target_ids(suite)):
                raise AuditError("测试集没有覆盖所选修复目标")
    elif kind == "verification_suite":
        from app.services.verification_suites import candidate_scope

        candidate_scope(audit.id, inputs["candidate_ids"])
    elif kind == "rule" and inputs.get("holdout_id"):
        from app.services.rule_holdouts import dataset

        try:
            data = dataset(inputs["holdout_id"])
        except AuditError as exc:
            raise AuditError(str(exc), code="invalid_input") from exc
        if (data["language"], data["purpose"]) != (audit.language, inputs["purpose"]):
            raise AuditError("独立样本集语言或用途不匹配", code="invalid_input")


def create_stage_run(
    session: Session,
    audit_id: UUID,
    owner_id: UUID,
    kind: str,
    inputs: dict,
    *,
    initial_result: dict | None = None,
    prompt_version: str | None = None,
    policy: dict | None = None,
) -> StageRun:
    owned_audit(session, audit_id, owner_id)
    run = session.exec(
        select(AuditRun).where(AuditRun.id == audit_id).with_for_update()
    ).one()
    inputs = validate_inputs(kind, inputs)
    version = prompt_version or default_version(kind)
    ready = (
        (
            kind in {"report", "verification_suite", "verification"}
            and run.status == "failed"
        )
        or run.status == "completed"
        or (
            run.status == "failed"
            and kind in {"review", "repair", "scout", "candidate_translation"}
            and run.coverage.get("dual_engine", {}).get("review_ready", False)
        )
    )
    if not ready:
        raise AuditError("需要先完成静态审计")
    active = session.exec(
        select(StageRun).where(
            StageRun.audit_id == audit_id,
            StageRun.kind == kind,
            StageRun.status.in_(["queued", "running"]),
        )
    ).first()
    if active:
        raise AuditError("该阶段已有正在执行的任务")
    validate_targets(session, run, kind, inputs)
    if kind == "verification":
        from app.services.repair_comparison import comparison_materials

        record = session.get(RepairRecord, UUID(inputs["repair_id"]))
        if record is None or record.audit_id != audit_id:
            raise AuditError("修复不存在", code="not_found")
        source_stage = session.get(StageRun, record.stage_id)
        if source_stage.status != "completed" or record.status == "accepted":
            raise AuditError("请等待补丁生成结束；已接受记录保留原验收")
        inputs = {
            **inputs,
            "identity": comparison_materials(record, inputs["suite_id"])[0],
        }
    if kind == "report":
        from app.services.report_generation import source_fingerprint
        from app.services.reports import build_report

        inputs = {"source_fingerprint": source_fingerprint(build_report(session, run))}
    stage = StageRun(
        audit_id=audit_id,
        kind=kind,
        inputs=inputs,
        result=initial_result or {},
        prompt_version=version,
        model_config_snapshot=policy if policy is not None else {},
    )
    session.add(stage)
    session.commit()
    session.refresh(stage)
    return stage
