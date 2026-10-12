"""Tie acceptance and resumed validation to the exact isolated candidate."""

import json

from app.adapters.artifacts import ArtifactStore
from app.adapters.snapshot import snapshot_digest
from app.domain.audit import AuditError
from app.services.context_materials import digest


def validate_application(directory, state, inputs):
    application = json.loads((directory / "application.json").read_text())
    if (
        application["identity"]["proposal_hash"] != state["proposal_hash"]
        or application["identity"]["allowed_paths"] != state["allowed_paths"]
        or application["workspace_hash"] != snapshot_digest(directory / "workspace")
        or application.get("diff_hash")
        != digest((directory / "repair.diff").read_text())
    ):
        raise AuditError("隔离候选或 Diff 已变化，验证失效")
    return {
        "application": application,
        "profile": inputs.validation_profile,
        "rescan": inputs.rescan,
    }


def verify_acceptance(record, audit):
    scope = record.validation.get("semantic_scope")
    if not scope:
        return  # Historical v1 records keep their original contract.
    directory = ArtifactStore().directory(str(record.stage_id))
    context = json.loads((directory / "repair-context.json").read_text())
    attempt = directory / f"attempt-{scope['attempts']}"
    receipt = json.loads((attempt / "validation-receipt.json").read_text())
    candidate = json.loads((attempt / "candidate.json").read_text())
    application = receipt["identity"]["application"]
    if (
        digest(context) != scope["context_hash"]
        or context["snapshot"] != audit.snapshot_hash
        or snapshot_digest(ArtifactStore().source(str(audit.source_run_id)))
        != audit.snapshot_hash
        or snapshot_digest(attempt / "workspace") != application["workspace_hash"]
        or digest(candidate) != application["identity"]["proposal_hash"]
        or candidate["changes"] != record.changes
        or digest((directory / "repair.diff").read_text()) != application["diff_hash"]
        or digest({k: v for k, v in record.validation.items() if k != "semantic_scope"})
        != receipt["checks_hash"]
    ):
        raise AuditError("补丁或验证身份已变化，请重新验证")
