"""Freeze platform comparison intent as an independent repair.verify request."""

import hashlib
from types import SimpleNamespace
from uuid import UUID

from semflow_contracts.common import EntityRef, SourceSnapshot
from semflow_contracts.runs import validate_spec
from semflow_research.public.implementation import code_digest
from semflow_research.public.runs import inspect
from semflow_research.public.runtime import ToolSettings
from sqlmodel import select

from app.core.audit_config import ROOT, audit_settings
from app.domain.audit import AuditError
from app.persistence.stage_models import RepairRecord, StageRun
from app.research_bridge.models import ResearchBinding
from app.research_bridge.requests import research_root
from app.research_bridge.suite_selection import selected_suite
from app.services.repair_comparison import comparison_materials


def freeze_verify(binding, stage, audit, session):
    binding.executor = "semflow-research/2"
    record = session.get(RepairRecord, UUID(stage.inputs["repair_id"]))
    if record is None or record.audit_id != audit.id:
        raise AuditError("修复不属于当前项目", code="not_found")
    if (
        comparison_materials(record, stage.inputs["suite_id"])[0]
        != stage.inputs["identity"]
    ):
        raise AuditError("排队期间修复或测试材料变化", code="integrity_error")
    producer = session.exec(
        select(ResearchBinding).where(ResearchBinding.stage_id == record.stage_id)
    ).one()
    receipt = inspect(producer.execution_id, root=research_root())
    result = receipt.result
    if result is None or result.patch is None or result.patched_source is None:
        raise AuditError("科研修复没有可验证的补丁", code="invalid_contract")
    snapshot = SourceSnapshot.model_validate(producer.request["source"])
    binding.entity_map = dict(producer.entity_map)
    source_stage = session.get(StageRun, record.stage_id)
    selection = SimpleNamespace(
        inputs={
            **source_stage.inputs,
            "verification_suite_id": stage.inputs["suite_id"],
        }
    )
    suite = selected_suite(
        binding,
        selection,
        audit,
        session,
        snapshot,
        producer.request["inputs"]["targets"],
    )
    values = {
        name: getattr(audit_settings, name)
        for name in ToolSettings.model_fields
        if hasattr(audit_settings, name)
    }
    values["ARTIFACT_ROOT"] = research_root()
    resources = ToolSettings.model_validate(values)
    reference = EntityRef(
        execution_id=producer.execution_id,
        entity_id=result.repair_id,
        bundle=receipt.manifest,
    )
    # WIRE-SEND:research.run — peer: runtime.repair_verify.receive / verify.
    # AGENT: bind the published repair/source/patch and exact suite. Platform
    # comparison identity remains a compatibility namespace, never a core hash.
    spec = validate_spec(
        {
            "execution_id": str(binding.execution_id),
            "module": "repair",
            "operation": "verify",
            "lineage": {},
            "source": snapshot.model_dump(mode="json"),
            "language": audit.language,
            "implementation": {
                "method_id": "semflow.repair.verify",
                "method_version": "1",
                "code_digest": code_digest(),
                "dependency_lock_digest": hashlib.sha256(
                    (ROOT / "system/uv.lock").read_bytes()
                ).hexdigest(),
            },
            "model": None,
            "prompts": [],
            "policy": {
                "mode": "progress",
                "max_calls": None,
                "max_tokens": None,
                "max_seconds": None,
                "per_call_timeout_seconds": resources.AI_TIMEOUT,
                "tool_timeout_seconds": resources.VALIDATOR_TIMEOUT,
                "scan_timeout_seconds": resources.SCAN_TIMEOUT,
                "max_attempts": 1,
                "max_context_chars": resources.SEMANTIC_CONTEXT_CHARS,
                "resource_profile": "platform-frozen",
                "decision_policy": "human_only",
            },
            "inputs": {
                "repair": reference.model_dump(mode="json"),
                "patch": result.patch.model_dump(mode="json"),
                "patched_source": result.patched_source.model_dump(mode="json"),
                "suite": suite.model_dump(mode="json"),
                "validation_plan": {"syntax": False, "before_after": True},
            },
        }
    )
    binding.request, binding.resources, binding.legacy_source_digest = (
        spec.model_dump(mode="json"),
        resources.model_dump(mode="json"),
        audit.snapshot_hash,
    )
    return spec
