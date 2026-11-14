"""Explicit conversion from scientific identities into legacy validation DTOs."""

from copy import deepcopy
from uuid import UUID

from app.adapters.artifacts import ArtifactStore
from app.adapters.snapshot import snapshot_digest
from app.persistence.stage_models import StageRun


def identity(session, binding, stage, result):
    suite_id = stage.inputs.get("verification_suite_id")
    suite = session.get(StageRun, UUID(suite_id)) if suite_id else None
    workspace = ArtifactStore().directory(str(stage.id)) / "workspace"
    return {
        "audit_id": str(stage.audit_id),
        "stage_id": str(stage.id),
        "source_snapshot": binding.legacy_source_digest,
        "patched_snapshot": snapshot_digest(workspace)
        if result.patched_source
        else None,
        "suite_id": suite_id,
        "suite_hash": suite.result["suite_hash"] if suite else None,
        "test_files_hash": suite.result["test_files_hash"] if suite else None,
    }


def project(checks, compatibility):
    # Peer: repair_projection.validation_view / repair_integrity.verify_if_bound.
    # AGENT: legacy hashes and IDs keep their old meaning. Retain the original
    # scientific identity separately; never substitute one 64-character digest
    # or UUID for another just because its JSON representation has the same shape.
    checks = deepcopy(checks)
    for check in checks.values():
        if "patched_snapshot_hash" in check:
            check["research_patched_tree_sha256"] = check["patched_snapshot_hash"]
            check["patched_snapshot_hash"] = compatibility["patched_snapshot"]
        if "identity" in check:
            check["research_identity"] = deepcopy(check["identity"])
            for key in (
                "suite_id",
                "suite_hash",
                "test_files_hash",
                "source_snapshot",
                "patched_snapshot",
            ):
                if key in check["identity"]:
                    check["identity"][key] = compatibility[key]
        if check.get("candidate_identity"):
            original = check["candidate_identity"]
            check["research_candidate_identity"] = original
            check["candidate_identity"] = {
                **{
                    k: v
                    for k, v in original.items()
                    if k not in {"snapshot_id", "execution_id", "patched_snapshot"}
                },
                "audit_id": compatibility["audit_id"],
                "stage_id": compatibility["stage_id"],
                "patched_snapshot": compatibility["patched_snapshot"],
            }
    return checks
