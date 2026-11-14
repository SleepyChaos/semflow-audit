"""Native repair boundary using frozen targets, scope and explicit method controls."""

from semflow_contracts.errors import ResearchError
from semflow_contracts.modelio.stages import RepairRequest

from semflow_research.runtime.bundle_io import import_targets
from semflow_research.runtime.repair_outputs import export


def validate_controls(spec, context=None):
    inputs = spec.inputs
    if inputs.engine == "openhands":
        if inputs.openhands is None:
            raise ResearchError("invalid_contract", "OpenHands policy is missing")
        if inputs.openhands.sdk_version != "1.56.0":
            raise ResearchError(
                "unsupported_version", "OpenHands SDK version is not supported"
            )
        # WIRE-RECV:research.openhands — peer: CLI/resources and platform repair_requests.
        # AGENT: missing SDK interpreter/image is a terminal resource failure;
        # never enter the graph and report an empty successful patch.
        if (
            not context.settings.OPENHANDS_PYTHON
            or not context.settings.OPENHANDS_IMAGE
        ):
            raise ResearchError(
                "tool_unavailable",
                "OpenHands interpreter and image resources are not available",
            )
        if context.settings.OPENHANDS_IMAGE != inputs.openhands.image_digest:
            raise ResearchError(
                "identity_mismatch", "OpenHands image differs from the frozen policy"
            )
        prompts = [p for p in spec.prompts if p.role == "repair_openhands"]
        if len(prompts) != 1 or prompts[0].version != str(
            inputs.openhands.prompt_version
        ):
            raise ResearchError(
                "invalid_contract", "OpenHands requires its exact frozen worker Prompt"
            )
    elif inputs.engine != "native":
        raise ResearchError("unsupported_operation", "Unknown repair engine")
    if (
        spec.implementation.method_version not in {"3", "4"}
        or inputs.method_policy.version != "1"
        or inputs.method_policy.feedback_policy.version != "1"
    ):
        raise ResearchError(
            "unsupported_version",
            "Unknown native repair method or feedback policy version",
        )
    if (
        inputs.validation_plan.before_after
        and not inputs.method_policy.selected_suite_feedback
    ):
        raise ResearchError(
            "unsupported_operation",
            "In-generation before/after requires selected-suite feedback; use public verify for independent comparison",
        )
    if inputs.method_policy.baseline_reuse and inputs.suite is None:
        raise ResearchError(
            "invalid_contract", "Baseline test reuse requires an explicit frozen suite"
        )
    if not inputs.method_policy.feedback_policy.stop_on_environment_error:
        raise ResearchError(
            "unsupported_operation",
            "Environment retry policy is not supported by this method version",
        )
    tests = inputs.validation_plan.project_tests
    if (
        tests
        and tests.runner
        != {"python": "python_pytest", "javascript": "javascript_test"}[spec.language]
    ):
        raise ResearchError(
            "invalid_contract",
            "Project test runner does not match the selected source language",
        )
    if tests and (
        tests.suite is not None
        or tests.resource_profile != spec.policy.resource_profile
    ):
        raise ResearchError(
            "unsupported_operation",
            "Project tests require the same explicit tool profile and no unmaterialized suite",
        )


def generate(context):
    validate_controls(context.spec, context)
    inputs = context.spec.inputs
    context, candidates = import_targets(
        context,
        inputs.targets.candidates,
        inputs.targets.evidence,
        decisions_ref=inputs.targets.decisions,
    )
    if inputs.validation_plan.rescan is not None:
        from semflow_research.runtime.repair_rescan import receive

        context = receive(context)
    for name in inputs.patch_scope.writable_paths:
        if name not in context.source.files:
            raise ResearchError(
                "unsupported_operation",
                "This native method requires explicit writable files, not an implicit directory expansion",
            )
    native = RepairRequest(
        engine=inputs.engine,
        candidate_ids=[row.candidate_id for row in candidates],
        allowed_paths=list(inputs.patch_scope.writable_paths),
        rescan=inputs.validation_plan.rescan is not None,
        verification_suite_id=inputs.suite.suite_id if inputs.suite else None,
        validation_profile=inputs.validation_plan.project_tests.runner
        if inputs.validation_plan.project_tests
        else "syntax",
    )
    context.execution_records.update(
        context.execution_id, inputs=native.model_dump(mode="json")
    )
    from semflow_research.graphs.repair import build_repair_graph
    from semflow_research.repair.repair import RepairService

    service = RepairService(str(context.execution_id), context.model, _kernel=context)
    graph = build_repair_graph(service, context.checkpoints, _kernel=context)
    try:
        graph.invoke(
            {"execution_id": str(context.execution_id)},
            {"configurable": {"thread_id": str(context.execution_id)}},
        )
    except Exception as error:
        if (
            inputs.engine == "openhands"
            and (context.workspace / "openhands-receipt.json").is_file()
        ):
            from semflow_contracts.common import ArtifactRef

            from semflow_research.adapters.repair.openhands_receipts import read

            reference = ArtifactRef.model_validate_json(
                (context.workspace / "openhands-receipt.json").read_bytes()
            )
            body = read(context.artifacts, reference, execution_id=context.execution_id)
            error.detail = reference
            error.artifacts = tuple(body.files.values())
        raise
    return export(context)
