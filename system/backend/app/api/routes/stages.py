"""Owned stage execution, immutable histories and human evidence-based confirmation."""

from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, HTTPException
from sqlmodel import select

from app.api.deps import LocalWorkspace, SessionDep
from app.api.routes.audits import owned_run
from app.contracts.stages import (
    DecisionRequest,
    RepairRequest,
    ReviewRequest,
    RuleRequest,
)
from app.domain.audit import AuditError
from app.jobs.stages import execute_stage
from app.models import get_datetime_utc
from app.persistence.audit_models import AuditRun
from app.persistence.stage_models import Candidate, Decision, Evidence, StageRun
from app.services.evidence import EvidenceService, valid_evidence

router = APIRouter(tags=["stages"])


def owned_stage(
    identifier: UUID, session: SessionDep, workspace: LocalWorkspace
) -> StageRun:
    stage = session.get(StageRun, identifier)
    if stage is None:
        raise HTTPException(404, "阶段执行不存在")
    owned_run(stage.audit_id, session, workspace)
    return stage


def dispatch_stage(stage: StageRun, session: SessionDep, resume: bool = False):
    try:
        execute_stage.delay(str(stage.id), resume)
    except Exception:
        stage.status, stage.error = "failed", "阶段任务队列不可用，请恢复后创建新的执行"
        session.add(stage)
        session.commit()
    session.refresh(stage)


def create_stage(
    audit_id: UUID,
    kind: str,
    inputs: dict,
    session: SessionDep,
    workspace: LocalWorkspace,
    *,
    initial_result: dict | None = None,
    prompt_version: str | None = None,
):
    owned_run(audit_id, session, workspace)
    run = session.exec(
        select(AuditRun).where(AuditRun.id == audit_id).with_for_update()
    ).one()
    if kind not in {
        "review",
        "repair",
        "rule",
        "scout",
        "report",
        "verification_suite",
        "verification",
        "candidate_translation",
    }:
        raise HTTPException(409, "此记录不支持后台重跑")
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
        raise HTTPException(409, "需要先完成静态审计")
    active = session.exec(
        select(StageRun).where(
            StageRun.audit_id == audit_id,
            StageRun.kind == kind,
            StageRun.status.in_(["queued", "running"]),
        )
    ).first()
    if active:
        raise HTTPException(409, "该阶段已有正在执行的任务")
    if kind == "verification":
        from app.persistence.stage_models import RepairRecord
        from app.services.repair_comparison import comparison_materials

        record = session.get(RepairRecord, UUID(inputs["repair_id"]))
        if record is None or record.audit_id != audit_id:
            raise HTTPException(404, "修复不存在")
        try:
            inputs = {
                **inputs,
                "identity": comparison_materials(record, inputs["suite_id"])[0],
            }
        except (AuditError, OSError, ValueError, KeyError) as exc:
            raise HTTPException(409, str(exc)) from exc
    if kind == "report":
        from app.services.report_generation import source_fingerprint
        from app.services.reports import build_report

        inputs = {"source_fingerprint": source_fingerprint(build_report(session, run))}
    stage = StageRun(
        audit_id=audit_id,
        kind=kind,
        inputs=inputs,
        result=initial_result or {},
        prompt_version=prompt_version
        or {
            "review": "12",
            "repair": "3",
            "rule": "8",
            "scout": "7",
            "report": "2",
            "verification_suite": "1",
            "verification": "1",
            "candidate_translation": "1",
        }[kind],
    )
    session.add(stage)
    session.commit()
    session.refresh(stage)
    dispatch_stage(stage, session)
    return stage


@router.get("/audits/{audit_id}/stages")
def stages(audit_id: UUID, session: SessionDep, workspace: LocalWorkspace):
    owned_run(audit_id, session, workspace)
    return session.exec(
        select(StageRun)
        .where(StageRun.audit_id == audit_id)
        .order_by(StageRun.created_at.desc())
    ).all()


@router.post("/audits/{audit_id}/review", status_code=201)
def review(
    audit_id: UUID, body: ReviewRequest, session: SessionDep, workspace: LocalWorkspace
):
    return create_stage(
        audit_id, "review", body.model_dump(mode="json"), session, workspace
    )


@router.post("/audits/{audit_id}/scout", status_code=201)
def scout(audit_id: UUID, body: dict, session: SessionDep, workspace: LocalWorkspace):
    from app.contracts.scouting import ScoutRequest

    try:
        inputs = ScoutRequest.model_validate(body)
    except ValueError as exc:
        raise HTTPException(422, "粗筛范围或预算无效") from exc
    if inputs.continuation_from_id:
        raise HTTPException(422, "窗口补审请使用初审执行的补审入口")
    return create_stage(
        audit_id, "scout", inputs.model_dump(mode="json"), session, workspace
    )


@router.post("/stages/{identifier}/continue-scout", status_code=201)
def continue_scout(identifier: UUID, session: SessionDep, workspace: LocalWorkspace):
    from app.services.scout_continuation import continuation_inputs

    previous = owned_stage(identifier, session, workspace)
    audit = session.exec(
        select(AuditRun).where(AuditRun.id == previous.audit_id).with_for_update()
    ).one()
    try:
        inputs, result = continuation_inputs(previous, audit, session)
    except (AuditError, KeyError, ValueError) as exc:
        raise HTTPException(409, str(exc)) from exc
    return create_stage(
        audit.id,
        "scout",
        inputs,
        session,
        workspace,
        initial_result=result,
        prompt_version=previous.prompt_version,
    )


@router.post("/audits/{audit_id}/repair", status_code=201)
def repair(
    audit_id: UUID, body: RepairRequest, session: SessionDep, workspace: LocalWorkspace
):
    owned_run(audit_id, session, workspace)
    candidates = session.exec(
        select(Candidate).where(
            Candidate.audit_id == audit_id, Candidate.id.in_(body.candidate_ids)
        )
    ).all()
    if len(candidates) != len(set(body.candidate_ids)) or any(
        row.status != "confirmed" for row in candidates
    ):
        raise HTTPException(409, "请选择本次审计中人工确认的缺陷")
    if body.verification_suite_id:
        from app.services.verification_suites import read_suite, target_ids

        try:
            suite = read_suite(body.verification_suite_id, audit_id)[1]
            if not set(map(str, body.candidate_ids)).issubset(target_ids(suite)):
                raise AuditError("测试集没有覆盖所选修复目标")
        except (AuditError, OSError, ValueError, KeyError) as exc:
            raise HTTPException(409, str(exc)) from exc
    return create_stage(
        audit_id, "repair", body.model_dump(mode="json"), session, workspace
    )


@router.post("/audits/{audit_id}/rule", status_code=201)
def rule(
    audit_id: UUID, body: RuleRequest, session: SessionDep, workspace: LocalWorkspace
):
    if body.holdout_id:
        from app.services.rule_holdouts import dataset

        try:
            data = dataset(body.holdout_id)
            audit = owned_run(audit_id, session, workspace)
            if (data["language"], data["purpose"]) != (audit.language, body.purpose):
                raise AuditError("独立样本集语言或用途不匹配")
        except AuditError as exc:
            raise HTTPException(422, str(exc)) from exc
    return create_stage(
        audit_id, "rule", body.model_dump(mode="json"), session, workspace
    )


@router.get("/stages/{identifier}")
def stage_detail(identifier: UUID, session: SessionDep, workspace: LocalWorkspace):
    return owned_stage(identifier, session, workspace)


@router.get("/stages/{identifier}/evidence")
def evidence(identifier: UUID, session: SessionDep, workspace: LocalWorkspace):
    owned_stage(identifier, session, workspace)
    return session.exec(select(Evidence).where(Evidence.stage_id == identifier)).all()


@router.post("/stages/{identifier}/retry", status_code=201)
def retry(identifier: UUID, session: SessionDep, workspace: LocalWorkspace):
    previous = owned_stage(identifier, session, workspace)
    if previous.status not in {"failed", "cancelled"}:
        raise HTTPException(409, "仅失败或取消阶段可创建重跑记录")
    if previous.kind == "scout" and previous.inputs.get("continuation_from_id"):
        return continue_scout(identifier, session, workspace)
    return create_stage(
        previous.audit_id, previous.kind, previous.inputs, session, workspace
    )


@router.post("/stages/{identifier}/cancel")
def cancel(identifier: UUID, session: SessionDep, workspace: LocalWorkspace):
    owned_stage(identifier, session, workspace)
    stage = session.exec(
        select(StageRun).where(StageRun.id == identifier).with_for_update()
    ).one()
    if stage.status not in {"queued", "running", "awaiting_confirmation"}:
        raise HTTPException(409, "阶段当前不能取消")
    stage.status, stage.phase = "cancelled", "cancel_requested"
    stage.updated_at = get_datetime_utc()
    session.add(stage)
    session.commit()
    return {
        "status": "cancelled",
        "meaning": "当前外部调用完成后停止，原始快照不受影响",
    }


@router.post("/stages/{identifier}/recover")
def recover(identifier: UUID, session: SessionDep, workspace: LocalWorkspace):
    owned_stage(identifier, session, workspace)
    stage = session.exec(
        select(StageRun).where(StageRun.id == identifier).with_for_update()
    ).one()
    if stage.status != "running" or stage.updated_at > get_datetime_utc() - timedelta(
        minutes=45
    ):
        raise HTTPException(409, "仅超过 45 分钟无更新的运行记录可标记失联")
    stage.status, stage.error = (
        "cancelled",
        "执行失联已回收；旧记录保留，可创建独立重试",
    )
    stage.updated_at = get_datetime_utc()
    session.add(stage)
    session.commit()
    session.refresh(stage)
    return stage


@router.get("/audits/{audit_id}/candidates")
def candidates(audit_id: UUID, session: SessionDep, workspace: LocalWorkspace):
    audit = owned_run(audit_id, session, workspace)
    from app.services.candidate_classification import classification_view
    from app.services.candidate_reviews import candidate_review
    from app.services.result_explanations import explain_candidate

    rows = session.exec(
        select(Candidate)
        .where(Candidate.audit_id == audit_id)
        .order_by(Candidate.created_at)
    ).all()
    sources = session.exec(select(Evidence).where(Evidence.audit_id == audit_id)).all()
    evidence_data = [row.model_dump(mode="json") for row in sources]
    stage_rows = session.exec(
        select(StageRun).where(StageRun.audit_id == audit_id)
    ).all()
    by_stage = {stage.id: stage for stage in stage_rows}
    decisions = session.exec(
        select(Decision)
        .join(Candidate, Candidate.id == Decision.candidate_id)
        .where(Candidate.audit_id == audit_id)
        .order_by(Decision.created_at)
    ).all()
    latest_decisions = {decision.candidate_id: decision for decision in decisions}
    from app.services.candidate_localization import localized_view

    def present(row):
        review = candidate_review(row, by_stage, audit.snapshot_hash)
        classification = classification_view(row, review, latest_decisions.get(row.id))
        payload = {
            **row.model_dump(mode="json"),
            "explanation": explain_candidate(
                row.model_dump(mode="json"), evidence_data
            ),
            "review": review,
            "classification": classification,
        }
        return localized_view(payload, by_stage)

    return [present(row) for row in rows]


@router.get("/candidates/{identifier}/decisions")
def decisions(identifier: UUID, session: SessionDep, workspace: LocalWorkspace):
    candidate = session.get(Candidate, identifier)
    if candidate is None:
        raise HTTPException(404, "候选不存在")
    owned_run(candidate.audit_id, session, workspace)
    return session.exec(
        select(Decision)
        .where(Decision.candidate_id == identifier)
        .order_by(Decision.created_at)
    ).all()


@router.post("/candidates/{identifier}/decisions", status_code=201)
def decide(
    identifier: UUID,
    body: DecisionRequest,
    session: SessionDep,
    workspace: LocalWorkspace,
):
    candidate = session.get(Candidate, identifier)
    if candidate is None:
        raise HTTPException(404, "候选不存在")
    owned_run(candidate.audit_id, session, workspace)
    stage = session.get(StageRun, candidate.stage_id)
    if stage.status in {"queued", "running"}:
        raise HTTPException(409, "请等待复审结束后记录人工判断")
    try:
        valid_evidence(
            candidate.audit_id,
            body.evidence_ids,
            body.status in {"confirmed", "excluded"},
        )
    except AuditError as exc:
        raise HTTPException(422, str(exc))
    decision = Decision(
        candidate_id=identifier,
        actor_id=workspace.id,
        status=body.status,
        reason=body.reason,
        evidence_ids=list(map(str, body.evidence_ids)),
    )
    candidate.status = body.status
    if body.evidence_ids:
        candidate.evidence_ids = list(map(str, body.evidence_ids))
    session.add(candidate)
    session.add(decision)
    session.commit()
    session.refresh(decision)
    return decision


@router.post("/audits/{audit_id}/evidence", status_code=201)
def manual_evidence(
    audit_id: UUID,
    file: str,
    session: SessionDep,
    workspace: LocalWorkspace,
    start_line: int = 1,
    end_line: int = 40,
):
    owned_run(audit_id, session, workspace)
    stage = StageRun(
        audit_id=audit_id,
        kind="manual_evidence",
        status="completed",
        phase="human_evidence",
    )
    session.add(stage)
    session.commit()
    session.refresh(stage)
    try:
        return EvidenceService(str(audit_id), str(stage.id), []).read(
            file, start_line, end_line
        )
    except AuditError as exc:
        stage.status, stage.error = "failed", str(exc)
        session.add(stage)
        session.commit()
        raise HTTPException(422, str(exc))


@router.get("/audits/{audit_id}/evidence")
def all_evidence(audit_id: UUID, session: SessionDep, workspace: LocalWorkspace):
    owned_run(audit_id, session, workspace)
    return session.exec(
        select(Evidence)
        .where(Evidence.audit_id == audit_id)
        .order_by(Evidence.created_at.desc())
        .limit(300)
    ).all()


@router.get("/stages/{identifier}/logs")
def stage_logs(identifier: UUID, session: SessionDep, workspace: LocalWorkspace):
    owned_stage(identifier, session, workspace)
    from app.adapters.artifacts import ArtifactStore

    return {"text": ArtifactStore().log_tail(str(identifier))}


@router.get("/stages/{identifier}/materials")
def stage_materials(identifier: UUID, session: SessionDep, workspace: LocalWorkspace):
    stage = owned_stage(identifier, session, workspace)
    import json

    from app.adapters.artifacts import ArtifactStore

    name = {"repair": "repair-context.json", "rule": "rule-materials.json"}.get(
        stage.kind
    )
    if stage.kind == "scout":
        name = "scout-map.json"
    elif stage.kind == "review" and stage.prompt_version in {
        "4",
        "5",
        "6",
        "7",
        "8",
        "9",
        "10",
        "11",
        "12",
    }:
        name = "review-pool.json"
    if not name:
        raise HTTPException(404, "此阶段没有语义材料")
    path = ArtifactStore().directory(str(identifier)) / name
    if not path.is_file():
        raise HTTPException(404, "材料尚未准备完成")
    return json.loads(path.read_text())
