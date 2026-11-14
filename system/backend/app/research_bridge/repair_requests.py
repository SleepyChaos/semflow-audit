"""Freeze platform confirmed candidates into the native repair contract."""

import hashlib

from semflow_contracts.repair import OpenHandsPolicy
from semflow_contracts.runs import validate_spec
from semflow_research.public.artifacts import commit
from semflow_research.public.implementation import code_digest
from semflow_research.public.runtime import ToolSettings

from app.adapters.ai.repair_policy import validate as validate_policy
from app.adapters.snapshot import snapshot_digest
from app.core.audit_config import ROOT, audit_settings
from app.domain.audit import AuditError
from app.research_bridge.repair_inputs import freeze_targets
from app.research_bridge.requests import research_root


def freeze_repair(binding, stage, audit, session):
    binding.executor = "semflow-research/2"
    engine = stage.inputs.get("engine", "native")
    if engine not in {"native", "openhands"}:
        raise AuditError("未知修复引擎", code="invalid_contract")
    from app.research_bridge.suite_requests import source_for

    source_root, snapshot = source_for(binding, audit, session)
    if snapshot_digest(source_root) != audit.snapshot_hash:
        raise AuditError("捕获期间平台原快照变化", code="integrity_error")
    rescan, static_refs = {}, None
    if stage.inputs.get("rescan"):
        from app.research_bridge.repair_baseline import freeze

        snapshot, rescan, static_refs = freeze(
            binding, audit, session, snapshot, source_root
        )
    targets, candidates = freeze_targets(
        binding, stage, audit, session, snapshot, source_root, static_refs=static_refs
    )
    suite = None
    if stage.inputs.get("verification_suite_id"):
        from app.research_bridge.suite_selection import selected_suite

        suite = selected_suite(binding, stage, audit, session, snapshot, targets)
    args = {"root": research_root(), "execution_id": binding.execution_id}
    paths = tuple(
        dict.fromkeys(
            stage.inputs.get("allowed_paths")
            or [row.location["file"] for row in candidates]
        )
    )
    readable_paths = tuple(dict.fromkeys(stage.inputs.get("readable_paths") or paths))
    if not set(paths).issubset(set(readable_paths)):
        raise AuditError(
            "writable_paths 必须包含在 readable_paths 中", code="invalid_contract"
        )
    policy = stage.model_config_snapshot
    if not policy or "prompt_snapshot" not in policy or "semantic_policy" not in policy:
        raise AuditError(
            "新修复缺少冻结模型、方法或 Prompt 策略", code="invalid_contract"
        )
    semantic = validate_policy(policy["semantic_policy"])
    if semantic.get("source_budget_version") != 1:
        raise AuditError(
            "未声明初始/总取证预算的旧策略不能转为新执行", code="unsupported_version"
        )
    prompt = policy["prompt_snapshot"]
    if (
        prompt["purpose"] != "repair"
        or prompt["version"] != stage.prompt_version
        or hashlib.sha256(prompt["content"].encode()).hexdigest() != prompt["sha256"]
    ):
        raise AuditError("修复 Prompt 冻结身份不一致", code="integrity_error")
    prompt_ref = commit(
        prompt["content"].encode(),
        kind="prompt",
        schema_version="prompt/1",
        media_type="text/plain",
        **args,
    )
    model = policy["model"]
    resources_values = {
        name: getattr(audit_settings, name)
        for name in ToolSettings.model_fields
        if hasattr(audit_settings, name)
    }
    resources_values.update(
        ARTIFACT_ROOT=research_root(),
        AI_BASE_URL=policy["base_url"],
        AI_MODEL=model,
        AI_TIMEOUT=policy["timeout"],
        SCAN_TIMEOUT=audit_settings.SCAN_TIMEOUT,
        VALIDATOR_TIMEOUT=audit_settings.VALIDATOR_TIMEOUT,
    )
    if engine == "openhands":
        hands = policy.get("openhands") or stage.inputs.get("openhands") or {}
        image = hands.get("image_digest") or resources_values.get("OPENHANDS_IMAGE", "")
        if not image.startswith("sha256:"):
            raise AuditError(
                "OpenHands 镜像资源不可用；必须冻结 sha256 digest",
                code="resource_unavailable",
            )
        if not resources_values.get("OPENHANDS_PYTHON"):
            raise AuditError(
                "OpenHands SDK interpreter 未配置", code="resource_unavailable"
            )
        openhands_policy = OpenHandsPolicy(
            image_digest=image,
            model=hands.get("model", model),
            endpoint_profile=hands.get("endpoint_profile", "platform-frozen"),
            prompt_version=int(hands.get("prompt_version", 3)),
            max_steps=int(hands.get("max_steps", audit_settings.OPENHANDS_MAX_STEPS)),
            timeout_seconds=int(
                hands.get("timeout_seconds", policy["max_seconds"] or 1800)
            ),
            output_tokens=int(hands.get("output_tokens", policy["budgets"]["repair"])),
            thinking_mode=hands.get("thinking_mode", policy.get("thinking_mode")),
            dependency_environment=hands.get("dependency_environment"),
            dependency_tools=hands.get("dependency_tools"),
            development_command=hands.get("development_command"),
        )
    else:
        openhands_policy = None
    prompts = [
        {
            "role": "repair",
            "template_id": "repair",
            "version": prompt["version"],
            "content": prompt_ref.model_dump(mode="json"),
            "sha256": prompt_ref.sha256,
        }
    ]
    if openhands_policy:
        from semflow_research.public.artifacts import LocalArtifacts
        from semflow_research.public.prompts import freeze_openhands_prompt

        prompts.append(
            freeze_openhands_prompt(
                version=openhands_policy.prompt_version,
                artifacts=LocalArtifacts(
                    research_root() / "artifacts", binding.execution_id
                ),
            ).model_dump(mode="json")
        )
        if openhands_policy.endpoint_profile != "platform-frozen":
            raise AuditError(
                "OpenHands endpoint profile 与冻结平台资源不一致",
                code="invalid_contract",
            )
        resources_values.update(
            OPENHANDS_IMAGE=openhands_policy.image_digest,
            OPENHANDS_BASE_URL=policy["base_url"],
        )
    # WIRE-SEND:research.resources — peer: repair_runtime.execute_bound / factory.assemble.
    # AGENT: persist the full JSON-safe non-secret profile once. Recovery uses
    # these values, injecting credentials separately rather than current defaults.
    resources = ToolSettings.model_validate(resources_values)
    # WIRE-SEND:research.run — peer: factory.policy_for / repair_operations.generate.
    # AGENT: candidate attempts, initial/total source tools and model calls have
    # distinct meanings; update the receiving mapping and schema in the same change.
    spec = validate_spec(
        {
            "execution_id": str(binding.execution_id),
            "module": "repair",
            "operation": "generate",
            "lineage": {},
            "source": snapshot.model_dump(mode="json"),
            "language": audit.language,
            "implementation": {
                "method_id": f"semflow.repair.{engine}",
                "method_version": stage.prompt_version,
                "code_digest": code_digest(),
                "dependency_lock_digest": hashlib.sha256(
                    (ROOT / "system/uv.lock").read_bytes()
                ).hexdigest(),
            },
            "prompts": prompts,
            "model": {
                "provider": "openai-compatible",
                "model": model,
                "endpoint_profile": "platform-frozen",
                "output_schema_version": "1",
                "output_tokens": policy["budgets"]["repair"],
                "temperature": 0,
                "thinking_mode": policy.get("thinking_mode"),
            },
            "policy": {
                "mode": policy["execution_mode"],
                "max_calls": policy["max_calls"] or None,
                "max_tokens": policy["max_tokens"] or None,
                "max_seconds": policy["max_seconds"] or None,
                "per_call_timeout_seconds": policy["timeout"],
                "tool_timeout_seconds": resources.VALIDATOR_TIMEOUT,
                "scan_timeout_seconds": resources.SCAN_TIMEOUT,
                "max_attempts": 1 + policy["recovery_attempts"],
                "max_no_progress": policy["max_no_progress"],
                "max_context_chars": semantic["repair_context_max_chars"],
                "resource_profile": "platform-frozen",
                "decision_policy": "human_only",
            },
            "inputs": {
                "engine": engine,
                **(
                    {"openhands": openhands_policy.model_dump(mode="json")}
                    if openhands_policy
                    else {}
                ),
                **({"suite": suite.model_dump(mode="json")} if suite else {}),
                "targets": targets,
                "patch_scope": {
                    "writable_paths": list(paths),
                    "readable_paths": list(readable_paths),
                    "max_changed_files": stage.inputs.get("max_changed_files", 30),
                    "enforce_observed_ranges": True,
                },
                "validation_plan": {
                    **rescan,
                    "syntax": stage.inputs.get("validation_profile", "syntax")
                    == "syntax",
                    "project_tests": {
                        "runner": stage.inputs["validation_profile"],
                        "resource_profile": "platform-frozen",
                    }
                    if stage.inputs.get("validation_profile", "syntax") != "syntax"
                    else None,
                    "before_after": suite is not None,
                },
                "method_policy": {
                    "version": "1",
                    "max_candidates": semantic["repair_attempts"],
                    "model_call_limit": semantic["repair_call_limit"],
                    "inspection_limits": {
                        "max_steps": semantic["source_tool_limit"],
                        "initial_source_steps": semantic["initial_source_tool_limit"],
                        "max_context_chars": semantic["context_chars"],
                        "max_expanded_context_chars": semantic[
                            "repair_context_max_chars"
                        ],
                    },
                    "feedback_policy": {
                        "version": "1",
                        "semantic_consistency": True,
                        "refresh_understanding": True,
                        "stop_on_environment_error": True,
                    },
                    "selected_suite_feedback": suite is not None,
                    "baseline_reuse": suite is not None,
                },
            },
        }
    )
    binding.request, binding.resources = (
        spec.model_dump(mode="json"),
        resources.model_dump(mode="json"),
    )
    binding.legacy_source_digest = audit.snapshot_hash
    return spec
