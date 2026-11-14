"""Algorithm extracted from app.services.repair_integrity.

Runtime dependencies are passed explicitly; no platform ORM or configuration.
Changes to JSON require checking the corresponding semflow_contracts/wire peer.
"""

"""Tie acceptance and resumed validation to the exact isolated candidate."""
import json

from semflow_research.adapters.artifacts import ArtifactStore
from semflow_research.adapters.snapshot import snapshot_digest
from semflow_research.domain.errors import AuditError
from semflow_research.evidence.context_materials import digest


def validate_application(directory, state, inputs):
    application = json.loads((directory / "application.json").read_text())
    if (
        application["identity"]["proposal_hash"] != state["proposal_hash"]
        or application["identity"]["allowed_paths"] != state["allowed_paths"]
        or application["workspace_hash"] != snapshot_digest(directory / "workspace")
        or (
            application.get("diff_hash")
            != digest((directory / "repair.diff").read_text())
        )
    ):
        raise AuditError("隔离候选或 Diff 已变化，验证失效")
    return {
        "application": application,
        "profile": inputs.validation_profile,
        "rescan": inputs.rescan,
    }


def verify_acceptance(record, audit, *, _kernel):
    scope = record.validation.get("semantic_scope")
    if not scope:
        return
    directory = ArtifactStore(_kernel=_kernel).directory(str(record.execution_id))
    context = json.loads((directory / "repair-context.json").read_text())
    attempt = directory / f"attempt-{scope['attempts']}"
    receipt = json.loads((attempt / "validation-receipt.json").read_text())
    candidate = json.loads((attempt / "candidate.json").read_text())
    application = receipt["identity"]["application"]
    if (
        digest(context) != scope["context_hash"]
        or context["snapshot"] != audit.snapshot_hash
        or snapshot_digest(
            ArtifactStore(_kernel=_kernel).source(str(audit.snapshot_id))
        )
        != audit.snapshot_hash
        or (snapshot_digest(attempt / "workspace") != application["workspace_hash"])
        or (digest(candidate) != application["identity"]["proposal_hash"])
        or (candidate["changes"] != record.changes)
        or (digest((directory / "repair.diff").read_text()) != application["diff_hash"])
        or (
            digest(
                {k: v for k, v in record.validation.items() if k != "semantic_scope"}
            )
            != receipt["checks_hash"]
        )
    ):
        raise AuditError("补丁或验证身份已变化，请重新验证")
