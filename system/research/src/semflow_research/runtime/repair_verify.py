"""Independent native before/after validation over frozen repair and suite refs."""

import json
from uuid import uuid5

from semflow_contracts.common import ArtifactRef, canonical_bytes, digest
from semflow_contracts.errors import ResearchError
from semflow_contracts.repair import (
    ComparisonIdentity,
    RepairResult,
    RepairVerifyResult,
)
from semflow_contracts.results import ResultEnvelope, ResultManifest
from semflow_contracts.runs import validate_spec
from semflow_contracts.validation import CheckResult, ValidationReceipt

from semflow_research.adapters.repair.verification_runner import (
    resolve_image,
    run_suite,
)
from semflow_research.domain.errors import AuditError, ExecutionCancelled
from semflow_research.repair.verification_results import compare_runs
from semflow_research.runtime.bundle_reader import authorize_artifacts
from semflow_research.runtime.ledger import input_artifacts
from semflow_research.runtime.sources import materialize
from semflow_research.runtime.suite_inputs import materialize as suite_view


def receive(context):
    inputs = context.spec.inputs
    reference = inputs.repair
    if (
        reference.bundle.kind != "result_manifest"
        or reference.bundle.owner_execution_id != reference.execution_id
    ):
        raise ResearchError(
            "invalid_contract",
            "Repair verification requires the exact published result manifest",
        )
    # WIRE-RECV:research.manifest — peer: LocalLedger.publish / repair result caller.
    # AGENT: verify the original request and result before granting nested refs;
    # a different patch/source/target cannot be smuggled into an old repair ID.
    manifest = ResultManifest.model_validate_json(
        context.artifacts.read(reference.bundle)
    )
    original = context.executions.inspect(reference.execution_id)
    if (
        original is None
        or original.manifest != reference.bundle
        or manifest.execution_id != reference.execution_id
        or not isinstance(original.result, RepairResult)
        or original.result.repair_id != reference.entity_id
        or original.result.patch != inputs.patch
        or original.result.patched_source != inputs.patched_source
    ):
        raise ResearchError(
            "identity_mismatch", "Verification inputs differ from the published repair"
        )
    context = authorize_artifacts(context, (manifest.spec, manifest.result))
    spec = validate_spec(json.loads(context.artifacts.read(manifest.spec)))
    saved = ResultEnvelope.model_validate_json(context.artifacts.read(manifest.result))
    if saved.result != original.result or spec.source != context.spec.source:
        raise ResearchError(
            "identity_mismatch",
            "Repair verification source or immutable result changed",
        )
    context = authorize_artifacts(context, input_artifacts(spec))
    from semflow_research.runtime.bundle_io import import_targets

    context, _ = import_targets(
        context,
        spec.inputs.targets.candidates,
        spec.inputs.targets.evidence,
        decisions_ref=spec.inputs.targets.decisions,
    )
    targets = original.result.target_refs
    if not {r.model_dump_json() for r in targets}.issubset(
        r.model_dump_json() for r in inputs.suite.target_refs
    ):
        raise ResearchError(
            "identity_mismatch",
            "Selected suite does not cover the exact repair targets",
        )
    if inputs.validation_plan.rescan is not None:
        from semflow_research.runtime.repair_rescan import receive as scan_input

        context = scan_input(context)
    return context, original.result


def verify(context):
    if context.spec.implementation.method_version != "1":
        raise ResearchError(
            "unsupported_version", "Unknown independent comparison method"
        )
    inputs = context.spec.inputs
    if not inputs.validation_plan.before_after:
        raise ResearchError(
            "invalid_contract",
            "Independent verify requires requested before/after assertions",
        )
    context, repair = receive(context)
    patched = materialize(
        inputs.patched_source,
        artifacts=context.artifacts,
        execution_id=context.execution_id,
        target=context.workspace / "patched-source",
    )
    _, suite, tests = suite_view(context, inputs.suite)
    identity = ComparisonIdentity(
        before_tree_sha256=context.spec.source.tree_sha256,
        patch_sha256=inputs.patch.sha256,
        after_tree_sha256=inputs.patched_source.tree_sha256,
        suite_hash=inputs.suite.suite_hash,
        image_digest=inputs.suite.image_digest,
        target_digest=digest([r.model_dump(mode="json") for r in repair.target_refs]),
    )
    runs, checks = [], {}
    try:
        if resolve_image(inputs.suite.image_digest) != inputs.suite.image_digest:
            raise AuditError("Frozen suite image is unavailable")
        from semflow_research.adapters.repair.validator import validate_workspace

        if inputs.validation_plan.syntax:
            checks["syntax"] = validate_workspace(
                patched.root, context.spec.language, "syntax", _kernel=context
            )
        if inputs.validation_plan.project_tests:
            plan = inputs.validation_plan.project_tests
            expected = (
                "python_pytest"
                if context.spec.language == "python"
                else "javascript_test"
            )
            if (
                plan.runner != expected
                or plan.resource_profile != context.spec.policy.resource_profile
                or plan.suite
            ):
                raise ResearchError(
                    "invalid_contract", "Unsupported or mismatched project test profile"
                )
            checks["isolated_tests"] = validate_workspace(
                patched.root, context.spec.language, plan.runner, _kernel=context
            )
        if inputs.validation_plan.rescan:
            from types import SimpleNamespace

            from semflow_research.repair.rescan import check

            service = SimpleNamespace(
                directory=context.workspace,
                evidence=SimpleNamespace(
                    source_context=context.source_records.get(
                        context.spec.source.snapshot_id
                    )
                ),
                inputs=SimpleNamespace(
                    candidate_ids=[r.entity_id for r in repair.target_refs]
                ),
            )
            checks["rescan"] = check(
                service,
                patched.root,
                inputs.patched_source.tree_sha256,
                _kernel=context,
            )
        for ordinal in range(2):
            pair = {}
            for side, reader in (("before", context.source), ("after", patched)):
                context.control.check_active(context.execution_id)
                reader.verify_snapshot()
                pair[side] = run_suite(
                    reader.root,
                    tests,
                    suite,
                    identity.image_digest,
                    context.workspace / f"run-{ordinal + 1}-{side}",
                    _kernel=context,
                )
                context.control.check_active(context.execution_id)
            runs.append(pair)
        result = compare_runs(suite, runs)
    except ExecutionCancelled:
        raise
    except AuditError as exc:
        result = {
            "status": "error",
            "summary": str(exc),
            "cases": [],
            "meaning": "Execution failed; no remediation conclusion",
        }
    context.source.verify_snapshot()
    patched.verify_snapshot()
    suite_view(context, inputs.suite)  # reject assertion changes during execution
    if result["status"] == "passed" and any(
        row.get("status") not in {"passed", "not_run"} for row in checks.values()
    ):
        result["status"] = (
            "error"
            if any(r.get("status") in {"error", "blocked"} for r in checks.values())
            else "failed"
        )
    body = {
        **result,
        "identity": identity.model_dump(mode="json"),
        "runs": runs,
        "checks": checks,
        "suite": inputs.suite.model_dump(mode="json"),
        "repair": inputs.repair.model_dump(mode="json"),
    }
    raw = context.artifacts.commit(
        canonical_bytes(body),
        kind="validation_receipt",
        schema_version="semflow.repair-comparison/1",
    )
    status = result["status"]
    evidence = tuple(
        ArtifactRef.model_validate(ref)
        for pair in runs
        for run in pair.values()
        for ref in run.get("evidence_refs", ())
    )
    for ref in evidence:
        context.artifacts.read(ref)
    # WIRE-SEND:research.result — peer: comparison projection / CLI inspect.
    # AGENT: repeated assertion results establish only the specified technical
    # scope; preserve uncertainty and exact identity, never infer human acceptance.
    receipt = ValidationReceipt(
        validation_id=uuid5(context.execution_id, "before-after/1"),
        kind="before_after",
        status=status,
        subject_refs=(
            inputs.patch,
            inputs.patched_source.archive,
            inputs.suite.definition,
        ),
        target_refs=repair.target_refs,
        identity_digest=digest(identity),
        checks=(
            CheckResult(
                check_id="repeated_before_after",
                category="before_after",
                status=status,
                observed=raw,
                evidence=(raw, *evidence),
                reason=result.get("summary"),
            ),
        ),
        raw_output=raw,
        tool_profile=context.spec.policy.resource_profile,
        meaning=result["meaning"],
    )
    return RepairVerifyResult(
        repair_ref=inputs.repair, identity=identity, receipt=receipt
    )
