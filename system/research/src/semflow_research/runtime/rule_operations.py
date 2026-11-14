"""Assemble frozen rule inputs and drive the original RAG / LangGraph algorithm."""

from datetime import UTC, datetime
from uuid import uuid5

from langgraph.types import Command
from semflow_contracts.actions import ApprovalRequest, approval_subject_digest
from semflow_contracts.errors import ResearchError
from semflow_contracts.modelio.stages import RuleRequest

from semflow_research.runtime.bundle_io import import_targets
from semflow_research.runtime.corpus_inputs import materialize
from semflow_research.runtime.execution import KernelOutcome
from semflow_research.runtime.rule_outputs import (
    export,
    subject_refs,
    verify_saved_output,
)
from semflow_research.runtime.rule_toolchain import verify


def validate_controls(spec):
    if spec.operation != "generate" or spec.implementation.method_version != "8":
        raise ResearchError(
            "unsupported_operation",
            "This rule adapter supports method 8 generation and its checkpoint continuation",
        )
    inputs = spec.inputs
    if inputs.generation.version != "1" or inputs.retrieval.version != "1":
        raise ResearchError(
            "unsupported_version", "Unknown rule method or retrieval policy"
        )
    if not inputs.development.compile:
        raise ResearchError(
            "unsupported_operation", "Method 8 requires actual compilation"
        )
    if inputs.development.development_fixtures is not None:
        raise ResearchError(
            "unsupported_operation",
            "External development fixtures are not connected yet",
        )
    if inputs.development.project_replay and inputs.development.static_baseline is None:
        raise ResearchError(
            "invalid_contract",
            "Project replay requires the original immutable static baseline",
        )
    if not inputs.source_paths and inputs.target is None:
        raise ResearchError(
            "invalid_contract",
            "Rule generation needs explicit source paths or a confirmed target",
        )


def prepare_inputs(context):
    validate_controls(context.spec)
    verify(context)
    inputs = context.spec.inputs
    context = materialize(context, inputs.corpus)
    if inputs.development.project_replay:
        from semflow_research.runtime.rule_baseline import receive

        context = receive(context, inputs.development.static_baseline)
    candidates = ()
    if inputs.target is not None:
        context, candidates = import_targets(
            context,
            inputs.target.candidates,
            inputs.target.evidence,
            decisions_ref=inputs.target.decisions,
        )
        if len(candidates) != 1:
            raise ResearchError(
                "invalid_contract",
                "This rule method needs exactly one confirmed target",
            )
    native = RuleRequest(
        purpose=inputs.purpose,
        requirement=inputs.requirement,
        candidate_id=candidates[0].candidate_id if candidates else None,
        source_paths=list(inputs.source_paths),
        strategy=inputs.strategy,
        holdout_id=inputs.acceptance.holdout.dataset_id
        if inputs.acceptance.holdout
        else None,
    )
    if inputs.acceptance.holdout:
        from semflow_research.public.holdouts import select

        if select(inputs.acceptance.holdout.dataset_id) != inputs.acceptance.holdout:
            raise ResearchError(
                "identity_mismatch",
                "Independent holdout identity differs from frozen input",
            )
    context.execution_records.update(
        context.execution_id, inputs=native.model_dump(mode="json")
    )
    return context


def graph_for(context):
    from semflow_research.graphs.rules import build_rule_graph
    from semflow_research.rules.rules import RuleService

    service = RuleService(str(context.execution_id), context.model, _kernel=context)
    return build_rule_graph(service, context.checkpoints, _kernel=context)


def generate(context):
    context = prepare_inputs(context)
    graph = graph_for(context)
    try:
        state = graph.invoke(
            {"execution_id": str(context.execution_id)}, config(context)
        )
    except Exception as error:
        from semflow_research.runtime.rule_diagnostics import publish

        error.detail, error.artifacts = publish(context)
        raise
    return outcome(context, state)


def config(context):
    return {"configurable": {"thread_id": str(context.execution_id)}}


def outcome(context, state):
    output = export(context, state["rule_id"])
    if state.get("__interrupt__"):
        checkpoint = context.checkpoints.latest
        subjects = subject_refs(output)
        # WIRE-SEND:research.approval — peer: approvals.validate_resume / RuleService.approve.
        # AGENT: freeze every query/module/dependency/fixture plus latest native
        # checkpoint; model approval or partial subject hashes cannot replace this.
        request = ApprovalRequest(
            action_id=uuid5(context.execution_id, "fixtures/" + checkpoint.sha256),
            execution_id=context.execution_id,
            kind="approve_rule_fixtures",
            checkpoint=checkpoint,
            subject_refs=subjects,
            subject_digest=approval_subject_digest(subjects),
            created_at=datetime.now(UTC),
        )
        return KernelOutcome(output, pending_action=request)
    if state.get("approved") is False:
        output = output.model_copy(update={"outcome": "needs_revision"})
    return output


def validate_saved_resume(context, previous):
    """Preflight before consuming a control command or advancing graph state."""
    context = prepare_inputs(context)
    verify_saved_output(context, previous.result, previous.result.rule_id)
    graph = graph_for(context)
    state = graph.get_state(config(context))
    if state.next != ("approve_fixtures",) or not state.interrupts:
        raise ResearchError(
            "checkpoint_invalid", "Saved rule graph is not at its fixture approval gate"
        )
    if state.values.get("rule_id") != str(previous.result.rule_id):
        raise ResearchError(
            "approval_stale", "Checkpoint names a different scientific rule"
        )
    return context


def resume(context, command, previous):
    # The control boundary has transactionally accepted this exact decision;
    # LangGraph continues from the interrupt, never from generation START.
    graph = graph_for(context)
    try:
        state = graph.invoke(Command(resume=command.approval.approved), config(context))
    except Exception as error:
        from semflow_research.runtime.rule_diagnostics import publish

        error.detail, error.artifacts = publish(context)
        raise
    return outcome(context, state)
