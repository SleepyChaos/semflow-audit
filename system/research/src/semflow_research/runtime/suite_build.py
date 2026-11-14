"""Adapt the mature suite-generation method to explicit research inputs/results."""

from semflow_contracts.errors import ResearchError
from semflow_contracts.repair import SuiteBuildResult

from semflow_research.runtime.bundle_io import import_targets
from semflow_research.state.models import Candidate


def build(context):
    if context.spec.implementation.method_version != "2":
        raise ResearchError(
            "unsupported_version", "Public suite build requires the existing method 2"
        )
    inputs = context.spec.inputs
    if inputs.runtime_profile != context.spec.policy.resource_profile:
        raise ResearchError(
            "invalid_contract",
            "Suite runtime profile differs from frozen tool resources",
        )
    context, _ = import_targets(
        context,
        inputs.targets.candidates,
        inputs.targets.evidence,
        decisions_ref=inputs.targets.decisions,
    )
    if (
        inputs.requested_behavior.schema_version != "semflow.requested-behavior/1"
        or inputs.requested_behavior.media_type != "text/plain"
    ):
        raise ResearchError(
            "invalid_contract",
            "Suite behavior must be the declared raw UTF-8 text contract",
        )
    try:
        requirements = context.artifacts.read(inputs.requested_behavior).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ResearchError(
            "invalid_contract", "Suite behavior text must be valid UTF-8"
        ) from exc
    if len(requirements) > 4000:
        raise ResearchError(
            "invalid_contract",
            "Suite requested behavior exceeds the method input limit",
        )
    from semflow_contracts.modelio.verification import VerificationSuite

    from semflow_research.adapters.repair.verification_runner import resolve_image
    from semflow_research.public.suites import capture
    from semflow_research.repair.verification_suites import SuiteService

    image = resolve_image(
        context.settings.VALIDATOR_PYTHON_IMAGE
        if context.spec.language == "python"
        else context.settings.VALIDATOR_JS_IMAGE
    )
    candidates = context.records.list(Candidate)
    context.execution_records.update(
        context.execution_id,
        inputs={
            "candidate_ids": [str(c.id) for c in candidates],
            "requirements": requirements,
            "image": image,
        },
    )
    SuiteService(str(context.execution_id), context.model, _kernel=context).run()
    native = context.execution_records.get(context.execution_id).result
    suite = capture(
        definition=VerificationSuite.model_validate(native["suite"]),
        snapshot=context.spec.source,
        target_refs=tuple(c.source_ref for c in candidates),
        image_digest=image,
        source="model_generated",
        root=context.root,
        execution_id=context.execution_id,
        suite_id=context.execution_id,
        requirements=requirements,
    )
    return SuiteBuildResult(suite=suite, generation_evidence=inputs.targets.evidence)
