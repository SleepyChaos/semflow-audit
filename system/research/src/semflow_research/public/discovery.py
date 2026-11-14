"""Discovery public boundary: frozen request in, typed immutable receipt out."""

from semflow_contracts.errors import ResearchError
from semflow_contracts.runs import DiscoverySpec, validate_spec

from semflow_research.runtime.algorithm_context import AlgorithmContext
from semflow_research.runtime.execution import execute as run_execution


def execute(spec: DiscoverySpec, context: AlgorithmContext):
    spec = validate_spec(spec)
    if spec.module != "discovery" or context.execution_id != spec.execution_id:
        raise ResearchError(
            "identity_mismatch", "Discovery execution identity mismatch"
        )
    from semflow_research.runtime import discovery_operations

    handlers = {
        "scan": discovery_operations.scan,
        "scout": discovery_operations.scout,
        "review": discovery_operations.review,
    }
    if spec.operation == "discover":
        from semflow_research.runtime.dual_discovery import discover

        handlers["discover"] = discover
    if spec.operation not in handlers:
        raise ResearchError("unsupported_operation", "Unknown discovery operation")
    return run_execution(spec, context, handlers[spec.operation])


def child_execution_id(parent_id, role):
    from semflow_research.runtime.children import child_id

    if role not in {"scan", "scout", "review"}:
        raise ResearchError("invalid_contract", "Unknown discovery child role")
    return child_id(parent_id, role)
