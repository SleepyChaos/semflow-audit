"""Rule kernel boundary. Algorithm migration is tracked by DEC-008."""

from semflow_contracts.errors import ResearchError
from semflow_contracts.results import ResultEnvelope
from semflow_contracts.runs import RuleSpec, validate_spec

from semflow_research.runtime.algorithm_context import AlgorithmContext
from semflow_research.runtime.execution import execute as run_execution


def execute(spec: RuleSpec, context: AlgorithmContext) -> ResultEnvelope:
    validated = validate_spec(spec)
    if validated.module != "rules" or context.execution_id != validated.execution_id:
        raise ResearchError("identity_mismatch", "Rule execution identity mismatch")
    if validated.operation == "validate":
        from semflow_research.runtime.rule_validation import validate

        return run_execution(validated, context, validate)
    from semflow_research.runtime.rule_operations import generate, validate_controls

    validate_controls(validated)
    return run_execution(validated, context, generate)


def resume(spec: RuleSpec, context: AlgorithmContext, command) -> ResultEnvelope:
    from semflow_research.runtime.rule_operations import resume as continue_graph
    from semflow_research.runtime.rule_operations import validate_saved_resume

    spec = validate_spec(spec)
    if spec.module != "rules" or command.execution_id != spec.execution_id:
        raise ResearchError("identity_mismatch", "Resume names another rule execution")
    previous = context.executions.inspect(spec.execution_id)
    if previous and previous.execution_status == "awaiting_input":
        context = validate_saved_resume(context, previous)
    return run_execution(
        spec,
        context,
        lambda ctx: continue_graph(ctx, command, previous),
        resume_command=command,
    )
