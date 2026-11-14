"""Prepare an explicit immutable continuation request; platform chooses latestness."""

from semflow_contracts.common import canonical_bytes
from semflow_contracts.errors import ResearchError
from semflow_contracts.modelio.scouting import ScoutRequest
from semflow_contracts.scout_continuation import ScoutContinuation

from semflow_research.public.runs import inspect, specification
from semflow_research.runtime.artifacts import LocalArtifacts
from semflow_research.runtime.factory import internal_inputs


def capture(execution_id, *, root):
    previous = inspect(execution_id, root=root)
    spec = specification(execution_id, root=root)
    if (
        spec.operation != "scout"
        or spec.implementation.method_version not in {"4", "5", "6", "7", "8"}
        or previous is None
        or previous.result is None
        or previous.execution_status not in {"completed", "failed", "cancelled"}
    ):
        raise ResearchError(
            "invalid_contract", "A terminal scout receipt with a frozen map is required"
        )
    output = previous.result
    if output.project_map is None or output.analysis_trace is None:
        raise ResearchError(
            "invalid_contract",
            "Historical scout did not export a portable map and trace",
        )
    body = ScoutContinuation(
        previous_execution_id=execution_id,
        snapshot_id=spec.source.snapshot_id,
        source_digest=spec.source.tree_sha256,
        method_version=spec.implementation.method_version,
        code_digest=spec.implementation.code_digest,
        dependency_lock_digest=spec.implementation.dependency_lock_digest,
        manifest=previous.manifest,
        project_map=output.project_map,
        trace=output.analysis_trace,
        candidates=output.candidates,
        evidence=output.evidence,
        native_inputs=ScoutRequest.model_validate(internal_inputs(spec)),
    )
    # WIRE-SEND:research.scout_continuation — peer: runtime.scout_continuation.receive.
    # AGENT: inherit exact frozen inputs and map membership; no model call or
    # history mutation occurs here. A new RunSpec owns the additional work.
    return LocalArtifacts(root / "artifacts", execution_id).commit(
        canonical_bytes(body), kind="materials", schema_version=body.schema_version
    )
