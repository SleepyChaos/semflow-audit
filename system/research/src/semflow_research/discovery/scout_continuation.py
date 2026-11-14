"""Algorithm extracted from app.services.scout_continuation.

Runtime dependencies are passed explicitly; no platform ORM or configuration.
Changes to JSON require checking the corresponding semflow_contracts/wire peer.
"""

"""Continue an immutable scout map in a new execution, retaining completed receipts."""
import json
from types import SimpleNamespace

from semflow_contracts.modelio.scouting import ScoutRequest

from semflow_research.adapters.artifacts import ArtifactStore
from semflow_research.discovery.scout_inspection import eligible_units
from semflow_research.domain.errors import AuditError
from semflow_research.evidence.context_materials import digest
from semflow_research.evidence.evidence import EvidenceService
from semflow_research.state.models import ExecutionRecord


def frozen_map(previous, audit, *, _kernel):
    directory = ArtifactStore(_kernel=_kernel).directory(str(previous.id))
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


def continuation_inputs(previous, audit, session, *, _kernel):
    if previous.kind != "scout" or previous.status not in {
        "completed",
        "failed",
        "cancelled",
    }:
        raise AuditError("请等待 AI 初审结束后补审未完成窗口")
    if previous.method_version not in {"4", "5", "6", "7", "8"}:
        raise AuditError("该历史初审版本不支持窗口补审，请创建完整初审")
    latest = session.first(
        ExecutionRecord,
        snapshot_id=audit.id,
        kind="scout",
        _order="created_at",
        _descending=True,
    )
    if latest.id != previous.id:
        raise AuditError("已有更新的初审执行，请刷新后从最新执行补审")
    project = frozen_map(previous, audit, _kernel=_kernel)
    inputs = ScoutRequest.model_validate(previous.inputs)
    inputs.continuation_from_id = previous.id
    evidence = EvidenceService(
        str(audit.id), str(previous.id), inputs.paths, _kernel=_kernel
    )
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
    return (
        inputs.model_dump(mode="json"),
        {
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
        },
    )
