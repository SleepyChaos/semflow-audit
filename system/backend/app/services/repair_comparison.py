"""Version-bound execution of independent tests against original and patched copies."""

import json
from uuid import UUID

from sqlmodel import Session, select

from app.adapters.artifacts import ArtifactStore
from app.adapters.repair.verification_runner import resolve_image, run_suite
from app.adapters.snapshot import snapshot_digest
from app.core.db import engine
from app.domain.audit import AuditError
from app.persistence.audit_repository import AuditRepository
from app.persistence.stage_models import RepairRecord, StageRun
from app.persistence.stage_repository import StageRepository
from app.services.context_materials import digest, save_json
from app.services.repair_integrity import verify_acceptance
from app.services.verification_results import compare_runs
from app.services.verification_suites import candidate_scope, read_suite, target_ids


def comparison_materials(record, suite_id):
    audit = AuditRepository().get(str(record.audit_id))
    original = ArtifactStore().source(str(audit.source_run_id))
    repair_directory = ArtifactStore().directory(str(record.stage_id))
    attempt = record.validation.get("semantic_scope", {}).get("attempts")
    patched = (
        repair_directory / f"attempt-{attempt}" if attempt else repair_directory
    ) / "workspace"
    suite_stage, suite, tests = read_suite(suite_id, audit.id)
    if (
        not set(record.candidate_ids).issubset(target_ids(suite))
        or suite_stage.result["snapshot_hash"] != audit.snapshot_hash
    ):
        raise AuditError("测试集未覆盖全部修复目标，或不属于同一源码快照")
    candidate_scope(audit.id, record.candidate_ids)
    if not patched.is_dir() or snapshot_digest(original) != audit.snapshot_hash:
        raise AuditError("补丁副本不存在或原始快照已变化")
    verify_acceptance(record, audit)
    identity = {
        "audit_id": str(audit.id),
        "repair_id": str(record.id),
        "candidate_ids": sorted(record.candidate_ids),
        "source_snapshot": audit.snapshot_hash,
        "patched_snapshot": snapshot_digest(patched),
        "patch_hash": digest(
            {"changes": record.changes, "validation": record.validation}
        ),
        "diff_hash": digest(
            (repair_directory / "repair.diff").read_text(encoding="utf-8")
        ),
        "suite_id": str(suite_id),
        "suite_hash": suite_stage.result["suite_hash"],
        "test_files_hash": suite_stage.result["test_files_hash"],
    }
    return identity, original, patched, suite_stage, suite, tests


class ComparisonService:
    def __init__(self, stage_id):
        self.stage_id = stage_id
        self.repository = StageRepository()
        self.stage = self.repository.get(stage_id)
        self.directory = ArtifactStore().directory(stage_id)

    def run(self):
        with Session(engine) as session:
            record = session.get(RepairRecord, UUID(self.stage.inputs["repair_id"]))
            if record is None or record.audit_id != self.stage.audit_id:
                raise AuditError("修复记录不属于当前项目")
        self.repository.active(self.stage_id)
        identity, original, patched, suite_stage, suite, tests = comparison_materials(
            record, self.stage.inputs["suite_id"]
        )
        if identity != self.stage.inputs["identity"]:
            raise AuditError("排队期间材料发生变化，请新建对比")
        image_id = resolve_image(suite_stage.result["image"])
        runs = []
        for index in range(2):
            pair = {}
            for side, workspace in (("before", original), ("after", patched)):
                self.repository.active(self.stage_id)
                self.repository.update(
                    self.stage_id, phase=f"verify_{side}_{index + 1}"
                )
                pair[side] = run_suite(
                    workspace,
                    tests,
                    suite,
                    image_id,
                    self.directory / f"run-{index + 1}-{side}",
                )
            runs.append(pair)
        if comparison_materials(record, self.stage.inputs["suite_id"])[0] != identity:
            raise AuditError("测试期间快照、补丁或测试集变化，结果失效")
        result = {
            **compare_runs(suite, runs),
            "identity": identity,
            "image_id": image_id,
            "runs": runs,
            "suite_created_before_repair": suite_stage.created_at
            <= StageRepository().get(str(record.stage_id)).created_at,
            "suite_title": suite.title,
            "test_origin": suite_stage.result["origin"],
            "assumptions": suite.assumptions,
            "human_test_review_required": True,
        }
        result["receipt_hash"] = digest(result)
        save_json(self.directory / "comparison.json", result)
        self.repository.update(
            self.stage_id, status="completed", phase="verification_ready", result=result
        )


def comparison_state(session, record, *, verify=True):
    rows = session.exec(
        select(StageRun)
        .where(StageRun.audit_id == record.audit_id, StageRun.kind == "verification")
        .order_by(StageRun.created_at.desc())
    ).all()
    stage = next(
        (row for row in rows if row.inputs.get("repair_id") == str(record.id)), None
    )
    if stage is None:
        return {
            "status": "missing",
            "summary": "尚未对同一组测试执行修复前后对比，不能确认修复有效。",
        }
    if stage.status != "completed":
        return {
            "status": stage.status,
            "stage_id": str(stage.id),
            "error": stage.error,
            "summary": "前后对比尚未完成，请查看执行历史。",
        }
    result = stage.result
    if verify:
        try:
            saved = json.loads(
                (
                    ArtifactStore().directory(str(stage.id)) / "comparison.json"
                ).read_text(encoding="utf-8")
            )
            without_hash = {
                key: value for key, value in result.items() if key != "receipt_hash"
            }
            if (
                saved != result
                or digest(without_hash) != result["receipt_hash"]
                or comparison_materials(record, stage.inputs["suite_id"])[0]
                != result["identity"]
            ):
                raise AuditError("对比身份或产物变化")
        except AuditError, OSError, KeyError, ValueError:
            return {
                "status": "stale",
                "stage_id": str(stage.id),
                "summary": "源码、补丁、测试或证据记录已变化，请重新运行前后对比。",
            }
    return {**result, "stage_id": str(stage.id)}


def acceptance_ready(record, comparison):
    if comparison.get("status") != "passed":
        return False
    checks = record.validation
    if checks.get("isolated_tests", {}).get("status") != "passed":
        return False
    rescan = checks.get("rescan", {})
    return (
        rescan.get("status") == "passed"
        or (
            rescan.get("status") == "not_run"
            and not StageRepository()
            .get(str(record.stage_id))
            .inputs.get("rescan", True)
        )
        or (
            rescan.get("status") == "needs_review"
            and rescan.get("new_rule_alerts") == []
            and rescan.get("remaining_target_rules") == []
        )
    )


def _enqueue_after_repair(record_id, suite_id):
    if not suite_id:
        return
    from app.api.routes.stages import create_stage
    from app.persistence.workspace import Workspace

    with Session(engine) as session:
        record = session.get(RepairRecord, UUID(str(record_id)))
        audit = AuditRepository().get(str(record.audit_id))
        identity = comparison_materials(record, suite_id)[0]
        return create_stage(
            record.audit_id,
            "verification",
            {
                "repair_id": str(record.id),
                "suite_id": str(suite_id),
                "identity": identity,
            },
            session,
            Workspace(audit.owner_id),
        )


def enqueue_after_repair(record_id, suite_id):
    if not suite_id:
        return
    # Patch generation is already complete. A failed comparison dispatch must
    # not rewrite that completed history or discard the delivered patch.
    try:
        return _enqueue_after_repair(record_id, suite_id)
    except Exception:
        with Session(engine) as session:
            record = session.get(RepairRecord, UUID(str(record_id)))
            if record is None:
                return
            failed = StageRun(
                audit_id=record.audit_id,
                kind="verification",
                status="failed",
                phase="verification_not_started",
                inputs={"repair_id": str(record.id), "suite_id": str(suite_id)},
                error="自动前后对比未启动，请查看测试目标与任务队列后重新运行；已生成补丁保留。",
            )
            session.add(failed)
            session.commit()
            session.refresh(failed)
            return failed
