"""Recheck approved frozen rule bytes using the generation kernel's validator."""

import json
from dataclasses import replace

from semflow_contracts.errors import ResearchError
from semflow_contracts.modelio.stages import RuleRequest
from semflow_contracts.results import ResultManifest
from semflow_contracts.toolchains import RuleToolchain

from semflow_research.adapters.codeql.custom import query_digest
from semflow_research.rules.rules import RuleService
from semflow_research.runtime.approvals import validate_approval
from semflow_research.runtime.rule_diagnostics import publish, read
from semflow_research.runtime.rule_inputs import read_rule
from semflow_research.runtime.rule_outputs import receipt, subject_refs
from semflow_research.runtime.rule_toolchain import verify
from semflow_research.runtime.rule_validation_inputs import origin
from semflow_research.state.models import RuleVersion


def receive(context):
    # WIRE-RECV:research.run — peer: public.rule_validation.assemble / RuleValidateInput.
    # AGENT: preserve producer refs, original holdout and replay. Approval is of
    # exact fixtures; a new validation receipt cannot confirm a root or publish.
    inputs = context.spec.inputs
    store, generated, envelope = origin(context.artifacts, inputs.generation_manifest)
    output = envelope.result
    if (
        generated.implementation.method_version != "8"
        or context.spec.implementation != generated.implementation
        or context.spec.source != generated.source
        or context.spec.language != generated.language
        or inputs.rule.execution_id != envelope.execution_id
        or inputs.rule.entity_id != output.rule_id
        or inputs.rule.bundle
        != ResultManifest.model_validate_json(
            store.read(inputs.generation_manifest)
        ).result
        or inputs.query != output.rule
        or inputs.fixtures != output.fixtures
        or inputs.holdout != generated.inputs.acceptance.holdout
        or inputs.project_replay
        != (output.project_replay.raw_output if output.project_replay else None)
    ):
        raise ResearchError(
            "identity_mismatch",
            "Validation changed the original rule, source or evaluation selection",
        )
    context = replace(context, artifacts=store)
    if (
        not validate_approval(
            envelope.pending_action,
            inputs.approval,
            artifacts=store,
            checkpoint=envelope.pending_action.checkpoint,
        )
        or subject_refs(output) != envelope.pending_action.subject_refs
    ):
        raise ResearchError("approval_stale", "Validation subjects are not approved")
    if output.diagnostics is None:
        raise ResearchError(
            "invalid_contract", "Generation method diagnostics are missing"
        )
    diagnostic = read(store, output.diagnostics, envelope.execution_id)
    # Reuse the immutable generation method inputs for its existing validator.
    # The enclosing execution/published spec stays operation=validate; no graph,
    # retrieval or generation node runs, and the producer workspace is not read.
    algorithm = replace(
        context,
        spec=generated.model_copy(update={"execution_id": context.execution_id}),
    )
    verify(algorithm)
    query, modules, dependencies = read_rule(output.rule, store, context.spec.language)
    expected = RuleToolchain.model_validate_json(
        store.read(generated.inputs.development.query_pack)
    )
    if dependencies != expected.model_dump(mode="json")["dependencies"]:
        raise ResearchError(
            "identity_mismatch", "Rule dependencies differ from the frozen toolchain"
        )
    context.execution_records.update(
        context.execution_id,
        inputs=RuleRequest(
            purpose=output.purpose,
            requirement=generated.inputs.requirement,
            source_paths=list(generated.inputs.source_paths),
            strategy=generated.inputs.strategy,
            holdout_id=inputs.holdout.dataset_id if inputs.holdout else None,
        ).model_dump(mode="json"),
    )
    fixtures = json.loads(store.read(output.fixtures))
    context.records.save(
        RuleVersion(
            id=output.rule_id,
            execution_id=context.execution_id,
            snapshot_id=context.spec.source.snapshot_id,
            corpus_scope=context.spec.source.snapshot_id,
            language=context.spec.language,
            title=diagnostic.title or str(output.rule_id),
            purpose=output.purpose,
            strategy=output.strategy,
            query=query,
            modules=modules,
            dependencies=dependencies,
            query_hash=query_digest(query, modules),
            fixtures=fixtures,
            fixtures_approved=True,
            holdout_id=inputs.holdout.dataset_id if inputs.holdout else None,
            validation=diagnostic.validation,
        )
    )
    return algorithm, output


def validate(context):
    algorithm, original = receive(context)
    try:
        RuleService(str(context.execution_id), None, _kernel=algorithm).validate(
            {"rule_id": str(original.rule_id)}
        )
    except Exception as error:
        error.detail, error.artifacts = publish(context)
        raise
    current = context.records.get(RuleVersion, original.rule_id)
    raw = current.validation
    subjects = subject_refs(original)
    technical = receipt(
        context,
        "rule_development",
        {key: raw[key] for key in ("status", "tests", "codeql_version", "meaning")},
        subjects,
        name="approved_fixtures",
    )
    independent = receipt(context, "rule_holdout", raw["independent_holdout"], subjects)
    diagnostics, _ = publish(context, validation=raw, title=current.title)
    # WIRE-SEND:research.result — peer: ledger.inspect / RuleResult / platform projection.
    # AGENT: checks refer to original immutable subjects; original replay is
    # retained evidence, not a newly run replay. No holdout still means draft.
    return original.model_copy(
        update={
            "validation_semantics": "semflow.rule-validation/2",
            "technical_validation": technical,
            "independent_validation": independent,
            "diagnostics": diagnostics,
            "outcome": "checks_passed" if current.status == "validated" else "draft",
        }
    )
