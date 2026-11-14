"""Freeze authorized platform inputs for the original method-8 rule kernel."""

import hashlib
from types import SimpleNamespace

from semflow_contracts.common import digest
from semflow_contracts.runs import validate_spec
from semflow_research.public.artifacts import commit
from semflow_research.public.holdouts import select as select_holdout
from semflow_research.public.implementation import code_digest
from semflow_research.public.runtime import ToolSettings
from semflow_research.public.toolchains import capture as capture_toolchain

from app.core.audit_config import ROOT, audit_settings
from app.domain.audit import AuditError
from app.research_bridge.repair_baseline import freeze as freeze_baseline
from app.research_bridge.repair_inputs import freeze_targets
from app.research_bridge.requests import research_root
from app.research_bridge.rule_corpus import capture as capture_corpus
from app.research_bridge.rule_integrity import capture_baseline, capture_confirmation
from app.research_bridge.suite_requests import source_for


def freeze_rule(binding, stage, audit, session):
    source_root, snapshot = source_for(binding, audit, session)
    # The original method 8 always performs project replay. The normal Web DTO
    # has no switch to disable it. Missing baseline resources must remain errors.
    snapshot, baseline_payload, static_refs = freeze_baseline(
        binding, audit, session, snapshot, source_root
    )
    targets = None
    if stage.inputs.get("candidate_id"):
        target_inputs = {"candidate_ids": [stage.inputs["candidate_id"]]}
        targets, _ = freeze_targets(
            binding,
            SimpleNamespace(inputs=target_inputs),
            audit,
            session,
            snapshot,
            source_root,
            static_refs=static_refs,
        )
    policy = stage.model_config_snapshot
    if not policy or "prompt_snapshot" not in policy:
        raise AuditError("规则缺少冻结模型与 Prompt", code="invalid_contract")
    prompt = policy["prompt_snapshot"]
    if (
        prompt["purpose"] != "rule"
        or prompt["version"] != stage.prompt_version
        or hashlib.sha256(prompt["content"].encode()).hexdigest() != prompt["sha256"]
    ):
        raise AuditError("规则 Prompt 身份变化", code="integrity_error")
    prompt_ref = commit(
        prompt["content"].encode(),
        root=research_root(),
        execution_id=binding.execution_id,
        kind="prompt",
        schema_version="prompt/1",
    )
    values = {
        name: getattr(audit_settings, name)
        for name in ToolSettings.model_fields
        if hasattr(audit_settings, name)
    }
    values.update(
        ARTIFACT_ROOT=research_root(),
        AI_BASE_URL=policy["base_url"],
        AI_MODEL=policy["model"],
    )
    resources = ToolSettings.model_validate(values)
    exp = policy.get("rule_experiment", {})
    corpus, retrieval_mode = capture_corpus(session, binding, audit, resources, exp)
    toolchain = capture_toolchain(
        root=research_root(),
        owner_execution_id=binding.execution_id,
        language=audit.language,
        settings=resources,
    )
    holdout_id = stage.inputs.get("holdout_id")
    holdout = select_holdout(holdout_id).model_dump(mode="json") if holdout_id else None
    # WIRE-SEND:research.run — peer: factory.policy_for / rule_operations.prepare_inputs.
    # AGENT: freeze the existing method's defaults, explicit false flags and
    # independent holdout handle. Never disable replay or infer publication.
    flags = {
        name: exp.get(name, default)
        for name, default in {
            "full_feedback": True,
            "generation_constraint": True,
            "progress_feedback": True,
            "compact_context": True,
            "source_preparation_context": True,
            "rag_before_inspection": False,
        }.items()
    }
    spec = validate_spec(
        {
            "execution_id": str(binding.execution_id),
            "module": "rules",
            "operation": "generate",
            "lineage": {},
            "source": snapshot.model_dump(mode="json"),
            "language": audit.language,
            "implementation": {
                "method_id": "semflow.rules.rag",
                "method_version": stage.prompt_version,
                "code_digest": code_digest(),
                "dependency_lock_digest": hashlib.sha256(
                    (ROOT / "system/uv.lock").read_bytes()
                ).hexdigest(),
            },
            "prompts": [
                {
                    "role": "rule",
                    "template_id": "rule",
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
                "output_tokens": policy["budgets"]["rule"],
                "temperature": 0,
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
                "max_context_chars": policy.get("semantic_policy", {}).get(
                    "context_chars", resources.SEMANTIC_CONTEXT_CHARS
                ),
                "resource_profile": "platform-frozen",
                "decision_policy": "human_only",
            },
            "inputs": {
                "purpose": stage.inputs["purpose"],
                "requirement": stage.inputs["requirement"],
                "target": targets,
                "source_paths": stage.inputs.get("source_paths", []),
                "strategy": stage.inputs["strategy"],
                "corpus": corpus.model_dump(mode="json"),
                "retrieval": {
                    "mode": retrieval_mode,
                    "collection_routing": exp.get("collection_routing", True),
                    "corpus_document_ids": exp.get("corpus_document_ids"),
                    "top_k": exp.get("top_k", 6),
                    "version": "1",
                },
                "generation": {"version": "1", **flags},
                "development": {
                    "compile": True,
                    "project_replay": True,
                    "query_pack": toolchain.model_dump(mode="json"),
                    "static_baseline": baseline_payload["static_baseline"],
                },
                "acceptance": {"fixture_validation": True, "holdout": holdout},
            },
        }
    )
    binding.request, binding.resources = (
        spec.model_dump(mode="json"),
        resources.model_dump(mode="json"),
    )
    binding.legacy_source_digest = audit.snapshot_hash
    stage.result = {
        **stage.result,
        "research_input_confirmation": capture_confirmation(session, stage),
    }
    stage.result["research_platform_baseline"] = capture_baseline(audit)
    stage.result["research_platform_inputs_digest"] = digest(stage.inputs)
    return spec
