"""Continue an immutable scout map in a new execution, retaining completed receipts."""

import json
from types import SimpleNamespace

from sqlmodel import select

from app.adapters.artifacts import ArtifactStore
from app.contracts.scouting import ScoutRequest
from app.domain.audit import AuditError
from app.persistence.stage_models import StageRun
from app.services.context_materials import digest
from app.services.evidence import EvidenceService
from app.services.scout_inspection import eligible_units


def frozen_map(previous, audit):
    directory = ArtifactStore().directory(str(previous.id))
    try:
        project = json.loads((directory / "scout-map.json").read_text())
        receipt = json.loads((directory / "scout-map-receipt.json").read_text())
    except (OSError, ValueError) as exc:
        raise AuditError("原初审地图不可用，不能补审；请创建完整初审") from exc
    if project["snapshot"] != audit.snapshot_hash or receipt["identity"] != digest(
        {"project": project, "inputs": previous.inputs}
    ):
        raise AuditError("原初审地图或源码快照已变化，不能补审")
    return project


def continuation_inputs(previous, audit, session):
    if previous.kind != "scout" or previous.status not in {
        "completed",
        "failed",
        "cancelled",
    }:
        raise AuditError("请等待 AI 初审结束后补审未完成窗口")
    if previous.prompt_version not in {"4", "5", "6", "7", "8"}:
        raise AuditError("该历史初审版本不支持窗口补审，请创建完整初审")
    latest = session.exec(
        select(StageRun)
        .where(StageRun.audit_id == audit.id, StageRun.kind == "scout")
        .order_by(StageRun.created_at.desc())
    ).first()
    if latest.id != previous.id:
        raise AuditError("已有更新的初审执行，请刷新后从最新执行补审")
    project = frozen_map(previous, audit)
    inputs = ScoutRequest.model_validate(previous.inputs)
    inputs.continuation_from_id = previous.id
    # Reuse scope rules without rebuilding or reordering the immutable windows.
    evidence = EvidenceService(str(audit.id), str(previous.id), inputs.paths)
    eligible = eligible_units(
        SimpleNamespace(inputs=inputs, evidence=evidence), project
    )
    completed = [
        row for row in previous.result.get("units", []) if row["status"] == "inspected"
    ]
    done = {row["unit_id"] for row in completed}
    if not any(unit["id"] not in done for unit in eligible):
        raise AuditError("当前审计范围没有可补审的未完成窗口")
    lineage = list(
        dict.fromkeys([*previous.result.get("source_stage_ids", []), str(previous.id)])
    )
    return inputs.model_dump(mode="json"), {
        "units": completed,
        "source_stage_ids": lineage,
        "snapshot_hash": audit.snapshot_hash,
        "coverage": {
            "planned_windows": len(project["units"]),
            "continuable_windows": sum(unit["id"] not in done for unit in eligible),
        },
        "continuation": {
            "from_stage_id": str(previous.id),
            "inherited_windows": len(done),
            "inherited_unit_ids": sorted(done),
        },
    }
