"""Synthetic protocol examples; these references deliberately do not claim execution."""

from uuid import UUID

IDENTIFIER = "11111111-1111-4111-8111-111111111111"
SNAPSHOT = "22222222-2222-4222-8222-222222222222"


def ref(kind="source_archive", owner=IDENTIFIER):
    return {
        "artifact_id": "33333333-3333-4333-8333-333333333333",
        "owner_execution_id": str(owner),
        "kind": kind,
        "schema_version": "test/1",
        "path": f"objects/{kind}",
        "sha256": "0" * 64,
        "size_bytes": 0,
        "media_type": "application/json",
    }


def scan_spec(execution_id=IDENTIFIER):
    return {
        "schema_version": "semflow.research.run/1.0",
        "execution_id": str(execution_id),
        "module": "discovery",
        "operation": "scan",
        "lineage": {},
        "source": {
            "snapshot_id": SNAPSHOT,
            "tree_sha256": "0" * 64,
            "archive": ref(),
            "manifest": ref("source_manifest"),
            "languages": ["python"],
            "origin": {"kind": "archive"},
        },
        "language": "python",
        "implementation": {
            "method_id": "codeql",
            "method_version": "test-v1",
            "code_digest": "0" * 64,
            "dependency_lock_digest": "0" * 64,
        },
        "prompts": [],
        "model": None,
        "policy": {
            "mode": "bounded",
            "max_calls": 4,
            "max_tokens": 1000,
            "max_seconds": 30,
            "per_call_timeout_seconds": 10,
            "tool_timeout_seconds": 20,
            "max_attempts": 1,
            "max_context_chars": 4000,
            "resource_profile": "test-only",
            "decision_policy": "human_only",
        },
        "inputs": {
            "query_pack": {
                "name": "codeql/python-queries",
                "version": "test",
                "digest": "0" * 64,
            },
            "suite": {"name": "test", "digest": "0" * 64},
            "build_profile": "test-only",
        },
    }


def model_fields():
    return {
        "prompts": [
            {
                "role": "repair",
                "template_id": "repair",
                "version": "1",
                "content": ref("prompt"),
                "sha256": "0" * 64,
            }
        ],
        "model": {
            "provider": "test-only",
            "model": "scripted",
            "endpoint_profile": "test",
            "output_schema_version": "1",
        },
    }


def target_bundle():
    return {
        "snapshot_id": SNAPSHOT,
        "candidates": {"artifact": ref("candidate_bundle")},
        "evidence": {"artifact": ref("evidence_bundle")},
        "decisions": {"artifact": ref("decision_bundle")},
    }


def repair_spec():
    spec = scan_spec()
    spec.update(module="repair", operation="generate", **model_fields())
    spec["inputs"] = {
        "engine": "native",
        "targets": target_bundle(),
        "patch_scope": {
            "writable_paths": ["app.py"],
            "readable_paths": ["app.py"],
            "max_changed_files": 1,
        },
        "validation_plan": {"syntax": True, "before_after": False},
        "method_policy": {
            "version": "test-v1",
            "max_candidates": 1,
            "inspection_limits": {
                "max_steps": 3,
                "max_context_chars": 4000,
                "max_expanded_context_chars": 8000,
            },
            "feedback_policy": {
                "version": "1",
                "semantic_consistency": True,
                "refresh_understanding": True,
                "stop_on_environment_error": True,
            },
            "selected_suite_feedback": False,
            "baseline_reuse": False,
        },
    }
    return spec


def rules_spec():
    spec = scan_spec()
    spec.update(module="rules", operation="generate", **model_fields())
    spec["inputs"] = {
        "purpose": "vulnerability_detector",
        "requirement": "Detect untrusted input reaching eval",
        "strategy": "new_query",
        "corpus": {
            "snapshot_id": str(UUID(SNAPSHOT)),
            "manifest": ref("corpus_manifest"),
            "digest": "0" * 64,
            "collections": [
                {"name": name, "version": "1", "document_ids": [], "digest": "0" * 64}
                for name in ("reference", "rule_example")
            ],
        },
        "retrieval": {
            "mode": "bm25",
            "collection_routing": True,
            "top_k": 4,
            "version": "1",
        },
        "generation": {
            "version": "test-v1",
            "full_feedback": True,
            "generation_constraint": True,
            "progress_feedback": True,
            "compact_context": True,
            "source_preparation_context": True,
            "rag_before_inspection": False,
        },
        "development": {
            "compile": True,
            "project_replay": True,
            "query_pack": ref("dependencies"),
        },
        "acceptance": {"fixture_validation": True},
    }
    return spec
