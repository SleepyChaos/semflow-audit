"""Explicit platform scout settings to the same request consumed by the CLI."""

import hashlib
from pathlib import Path

from semflow_contracts.runs import validate_spec
from semflow_research.public.implementation import code_digest
from semflow_research.public.runs import capture_source
from semflow_research.public.runtime import ToolSettings

from app.adapters.artifacts import ArtifactStore
from app.adapters.snapshot import snapshot_digest
from app.core.audit_config import ROOT, audit_settings
from app.domain.audit import AuditError


def research_root():
    return audit_settings.ARTIFACT_ROOT / "research"


def freeze_stage(binding, stage, audit, *, session=None):
    from semflow_research.public.artifacts import commit

    root = research_root()
    source = ArtifactStore().source(str(audit.source_run_id))
    if snapshot_digest(source) != audit.snapshot_hash:
        raise AuditError("平台原快照已变化，不能转换为科研输入", code="integrity_error")
    snapshot = capture_source(
        source,
        root=root,
        owner_execution_id=binding.execution_id,
        languages=(audit.language,),
    )
    if snapshot_digest(source) != audit.snapshot_hash:
        raise AuditError("捕获期间平台原快照变化", code="integrity_error")
    if session is not None and stage.kind == "review":
        from semflow_contracts.common import SourceSnapshot
        from sqlmodel import select

        from app.research_bridge.models import ResearchAuditBinding

        scan_binding = session.exec(
            select(ResearchAuditBinding).where(
                ResearchAuditBinding.audit_id == audit.id
            )
        ).first()
        if scan_binding is not None and scan_binding.request:
            snapshot = SourceSnapshot.model_validate(scan_binding.request["source"])
    continuation = None
    if stage.kind == "scout" and stage.inputs.get("continuation_from_id"):
        from uuid import UUID

        from semflow_contracts.common import SourceSnapshot
        from semflow_research.public.scout_continuation import (
            capture as capture_continuation,
        )
        from sqlmodel import select

        from app.research_bridge.models import ResearchBinding

        parent = session.exec(
            select(ResearchBinding).where(
                ResearchBinding.stage_id == UUID(stage.inputs["continuation_from_id"])
            )
        ).one()
        snapshot = SourceSnapshot.model_validate(parent.request["source"])
        continuation = capture_continuation(parent.execution_id, root=root)
        binding.entity_map = {
            **parent.entity_map,
            "execution/" + str(parent.execution_id): str(parent.stage_id),
        }
    policy = stage.model_config_snapshot
    if not policy or "prompt_snapshot" not in policy:
        raise AuditError(
            "新科研执行缺少冻结平台模型策略或 Prompt", code="invalid_input"
        )
    prompt = policy["prompt_snapshot"]
    if (
        prompt["purpose"] != stage.kind
        or prompt["version"] != stage.prompt_version
        or hashlib.sha256(prompt["content"].encode()).hexdigest() != prompt["sha256"]
    ):
        raise AuditError("平台 Prompt 快照身份不一致", code="integrity_error")
    ref = commit(
        prompt["content"].encode(),
        root=root,
        execution_id=binding.execution_id,
        kind="prompt",
        schema_version="prompt/1",
        media_type="text/plain",
    )
    inputs = stage.inputs
    output_tokens = policy["budgets"][stage.kind]
    if stage.kind == "scout" and stage.prompt_version in {"6", "7", "8"}:
        output_tokens = max(6000, output_tokens)
    if stage.kind == "review" and int(stage.prompt_version) >= 6:
        output_tokens = min(8192, output_tokens)
    settings_values = {
        name: getattr(audit_settings, name)
        for name in ToolSettings.model_fields
        if hasattr(audit_settings, name)
    }
    settings_values.update(
        ARTIFACT_ROOT=root, AI_BASE_URL=policy["base_url"], AI_MODEL=policy["model"]
    )
    resources = ToolSettings(**settings_values)
    review_inputs = None
    if stage.kind == "review":
        from app.research_bridge.review_inputs import freeze_targets

        review_inputs = freeze_targets(session, binding, stage, audit, snapshot)
    # WIRE-SEND:research.run — peers: contracts.validate_spec / runtime.factory.
    # AGENT: preserve native scheduling, scope, Prompt and method independently;
    # explicit None means unbounded progress mode, never a hidden bounded default.
    spec = validate_spec(
        {
            "execution_id": str(binding.execution_id),
            "module": "discovery",
            "operation": stage.kind,
            "lineage": {},
            "source": snapshot.model_dump(mode="json"),
            "language": audit.language,
            "implementation": {
                "method_id": "semflow." + stage.kind,
                "method_version": stage.prompt_version,
                "code_digest": code_digest(),
                "dependency_lock_digest": hashlib.sha256(
                    (ROOT / "system/uv.lock").read_bytes()
                ).hexdigest(),
            },
            "prompts": [
                {
                    "role": stage.kind,
                    "template_id": stage.kind,
                    "version": prompt["version"],
                    "content": ref.model_dump(mode="json"),
                    "sha256": ref.sha256,
                }
            ],
            "model": {
                "provider": "openai-compatible",
                "model": policy["model"] or "unconfigured",
                "endpoint_profile": "platform-frozen",
                "output_schema_version": "1",
                "output_tokens": output_tokens,
                "thinking_mode": policy.get("thinking_mode"),
            },
            "policy": {
                "mode": policy.get("execution_mode", "bounded"),
                "max_calls": policy["max_calls"] or None,
                "max_tokens": policy["max_tokens"] or None,
                "max_seconds": policy["max_seconds"] or None,
                "per_call_timeout_seconds": policy["timeout"],
                "tool_timeout_seconds": resources.SCAN_TIMEOUT,
                "max_attempts": 1 + policy.get("recovery_attempts", 1),
                "max_no_progress": policy.get("max_no_progress", 3),
                "max_context_chars": inputs["max_context_chars"],
                "resource_profile": "platform-frozen",
                "decision_policy": "human_only",
            },
            "inputs": {
                "scope_paths": inputs["paths"],
                "continuation": continuation.model_dump(mode="json")
                if continuation
                else None,
                "inspection_paths": inputs["inspection_paths"],
                "scheduling_profile": inputs["scheduling_profile"],
                "include_third_party": inputs["include_third_party"],
                "window_lines": inputs["window_lines"],
                "window_policy": {
                    "version": "1",
                    "max_windows": inputs["max_units"],
                    "max_steps_per_window": inputs["steps_per_unit"],
                    "max_calls": policy["max_calls"] or None,
                },
            }
            if stage.kind == "scout"
            else review_inputs,
        }
    )
    binding.request, binding.resources = (
        spec.model_dump(mode="json"),
        resources.model_dump(mode="json"),
    )
    # Identity conversion is explicit: legacy hashes path+NUL+digest, research
    # hashes SourceManifest JSON. AGENT: do not substitute one hex string for the other.
    binding.legacy_source_digest = audit.snapshot_hash
    return spec, resources


def freeze_policy(kind, version, previous=None):
    from app.adapters.ai.policy import policy_snapshot

    policy = dict(previous or policy_snapshot(kind))
    if "prompt_snapshot" not in policy:
        path = (
            Path(__file__).resolve().parents[1] / "prompts" / f"{kind}.v{version}.txt"
        )
        text = path.read_text()
        policy["prompt_snapshot"] = {
            "purpose": kind,
            "version": version,
            "content": text,
            "sha256": hashlib.sha256(text.encode()).hexdigest(),
        }
    return policy
