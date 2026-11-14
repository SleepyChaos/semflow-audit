"""Repair public boundary; generated patches never accept themselves."""

from semflow_contracts.errors import ResearchError
from semflow_contracts.results import ResultEnvelope
from semflow_contracts.runs import RepairSpec, validate_spec

from semflow_research.runtime.algorithm_context import AlgorithmContext
from semflow_research.runtime.execution import execute as run_execution


def execute(spec: RepairSpec, context: AlgorithmContext) -> ResultEnvelope:
    spec = validate_spec(spec)
    if spec.module != "repair" or context.execution_id != spec.execution_id:
        raise ResearchError("identity_mismatch", "Repair execution identity mismatch")
    if spec.operation == "build_suite":
        from semflow_research.runtime.suite_build import build

        return run_execution(spec, context, build)
    if spec.operation == "generate":
        from semflow_research.runtime.repair_operations import generate

        return run_execution(spec, context, generate)
    from semflow_research.runtime.repair_verify import verify

    return run_execution(spec, context, verify)
