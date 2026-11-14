"""Caller policy/identity conversion for suite build and selected frozen suites."""

import hashlib
from uuid import uuid5

from semflow_contracts.common import SourceSnapshot
from semflow_contracts.runs import validate_spec
from semflow_research.public.artifacts import commit
from semflow_research.public.implementation import code_digest
from semflow_research.public.runs import capture_source
from semflow_research.public.runtime import ToolSettings
from sqlmodel import select

from app.adapters.artifacts import ArtifactStore
from app.adapters.snapshot import snapshot_digest
from app.core.audit_config import ROOT, audit_settings
from app.domain.audit import AuditError
from app.research_bridge.models import ResearchAuditBinding
from app.research_bridge.repair_inputs import freeze_targets
from app.research_bridge.requests import research_root


def source_for(binding, audit, session):
    source = ArtifactStore().source(str(audit.source_run_id))
    if snapshot_digest(source) != audit.snapshot_hash:
        raise AuditError("原始快照变化", code="integrity_error")
    scan = session.exec(
        select(ResearchAuditBinding).where(ResearchAuditBinding.audit_id == audit.id)
    ).first()
    snapshot = (
        SourceSnapshot.model_validate(scan.request["source"])
        if scan and scan.request
        else capture_source(
            source,
            root=research_root(),
            owner_execution_id=binding.execution_id,
            languages=(audit.language,),
        )
    )
    if not scan or not scan.request:
        # Peer: repair_requests / public capture_source. This deterministic caller
        # conversion names the same verified legacy source across suite/repair;
        # the canonical content digest and each archive reference remain explicit.
        snapshot = snapshot.model_copy(
            update={
                "snapshot_id": uuid5(
                    audit.source_run_id, "research-source/" + snapshot.tree_sha256
                )
            }
        )
    return source, snapshot


def freeze_build(binding, stage, audit, session):
    binding.executor = "semflow-research/2"
    source, snapshot = source_for(binding, audit, session)
    targets, _ = freeze_targets(binding, stage, audit, session, snapshot, source)
    policy = stage.model_config_snapshot
    prompt = policy["prompt_snapshot"]
    if (
        prompt["purpose"] != "verification_suite"
        or prompt["version"] != stage.prompt_version
        or hashlib.sha256(prompt["content"].encode()).hexdigest() != prompt["sha256"]
    ):
        raise AuditError("测试生成 Prompt 身份不一致", code="integrity_error")
    arguments = {"root": research_root(), "execution_id": binding.execution_id}
    resources = ToolSettings.model_validate(
        {
            name: getattr(audit_settings, name)
            for name in ToolSettings.model_fields
            if hasattr(audit_settings, name)
        }
        | {
            "ARTIFACT_ROOT": research_root(),
            "AI_BASE_URL": policy["base_url"],
            "AI_MODEL": policy["model"],
            "AI_TIMEOUT": policy["timeout"],
            **(
                {
                    "VALIDATOR_PYTHON_IMAGE"
                    if audit.language == "python"
                    else "VALIDATOR_JS_IMAGE": stage.inputs["image"]
                }
                if stage.inputs.get("image")
                else {}
            ),
        }
    )
    prompt_ref = commit(
        prompt["content"].encode(),
        kind="prompt",
        schema_version="prompt/1",
        **arguments,
    )
    behavior = commit(
        stage.inputs.get("requirements", "").encode(),
        kind="materials",
        schema_version="semflow.requested-behavior/1",
        media_type="text/plain",
        **arguments,
    )
    spec = validate_spec(
        {
            "execution_id": str(binding.execution_id),
            "module": "repair",
            "operation": "build_suite",
            "lineage": {},
            "source": snapshot.model_dump(mode="json"),
            "language": audit.language,
            "implementation": {
                "method_id": "semflow.repair.suite",
                "method_version": stage.prompt_version,
                "code_digest": code_digest(),
                "dependency_lock_digest": hashlib.sha256(
                    (ROOT / "system/uv.lock").read_bytes()
                ).hexdigest(),
            },
            "prompts": [
                {
                    "role": "verification_suite",
                    "template_id": "verification_suite",
                    "version": prompt["version"],
                    "content": prompt_ref.model_dump(mode="json"),
                    "sha256": prompt_ref.sha256,
                }
            ],
            "model": {
                "provider": "openai-compatible",
                "model": policy["model"],
                "endpoint_profile": "platform-frozen",
                "output_schema_version": "1",
                "output_tokens": policy["budgets"]["verification_suite"],
                "temperature": 0,
                "thinking_mode": policy.get("thinking_mode"),
            },
            "policy": {
                "mode": "bounded",
                "max_calls": policy["max_calls"],
                "max_tokens": policy["max_tokens"],
                "max_seconds": policy["max_seconds"],
                "per_call_timeout_seconds": policy["timeout"],
                "tool_timeout_seconds": resources.VALIDATOR_TIMEOUT,
                "max_attempts": 1 + policy["recovery_attempts"],
                "max_context_chars": resources.SEMANTIC_CONTEXT_CHARS,
                "resource_profile": "platform-frozen",
                "decision_policy": "human_only",
            },
            "inputs": {
                "targets": targets,
                "requested_behavior": behavior.model_dump(mode="json"),
                "runtime_profile": "platform-frozen",
            },
        }
    )
    binding.request, binding.resources, binding.legacy_source_digest = (
        spec.model_dump(mode="json"),
        resources.model_dump(mode="json"),
        audit.snapshot_hash,
    )
    return spec
