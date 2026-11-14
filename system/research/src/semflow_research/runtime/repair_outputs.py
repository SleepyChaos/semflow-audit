"""Translate native repair history to explicit typed artifacts and check receipts."""

import json
from uuid import uuid5

from semflow_contracts.common import ArtifactRef, canonical_bytes, digest
from semflow_contracts.errors import ResearchError
from semflow_contracts.repair import AttemptRecord, RepairAttempts, RepairResult
from semflow_contracts.validation import CheckResult, ValidationReceipt

from semflow_research.runtime.sources import capture
from semflow_research.state.models import Candidate, RepairRecord

KINDS = {
    "syntax": "syntax",
    "isolated_tests": "project_tests",
    "rescan": "rescan",
    "semantic_contract": "semantic_consistency",
    "selected_suite": "before_after",
    "application": "patch_application",
    "environment": "syntax",
}
STATUS = {
    "passed": "passed",
    "failed": "failed",
    "blocked": "error",
    "needs_review": "inconclusive",
    "not_run": "not_run",
    "not_evaluated": "not_evaluated",
    "inconclusive": "inconclusive",
    "error": "error",
}


def commit(context, data, kind, version, media_type="application/json"):
    return context.artifacts.commit(
        data, kind=kind, schema_version=version, media_type=media_type
    )


def read_attempts(artifacts, ref, *, execution_id, snapshot_id):
    # WIRE-RECV:research.repair_attempts — peer: export below / ledger.inspect.
    # AGENT: verify immutable history, owner and source before interpreting a
    # selected attempt. Passing checks never imply a platform acceptance action.
    if (
        ref.kind != "repair_attempts"
        or ref.schema_version != "semflow.repair-attempts/1"
        or ref.owner_execution_id != execution_id
    ):
        raise ResearchError(
            "identity_mismatch",
            "Repair attempt reference has a different producer or format",
        )
    body = RepairAttempts.model_validate_json(artifacts.read(ref))
    if body.execution_id != execution_id or body.snapshot_id != snapshot_id:
        raise ResearchError(
            "identity_mismatch",
            "Repair attempts belong to another execution or source snapshot",
        )
    from semflow_research.runtime.ledger import input_artifacts

    for nested in input_artifacts(body):
        artifacts.read(nested)
    from semflow_research.adapters.repair.openhands_receipts import read

    for attempt in body.records:
        if attempt.engine_receipt:
            if attempt.engine_receipt.schema_version == "semflow.openhands-usage/1":
                # Historical experimental output retained metrics only. Keep it
                # readable without claiming the newer complete worker receipt.
                artifacts.read(attempt.engine_receipt)
            else:
                read(artifacts, attempt.engine_receipt, execution_id=execution_id)
    return body


def receipts(context, checks, *, proposal, patch, source, targets, ordinal):
    result = []
    for name, check in checks.items():
        if name == "rescan" and context.spec.inputs.validation_plan.rescan is None:
            continue  # Unrequested controls are in RunSpec, never recorded as passing.
        if name not in KINDS:
            continue
        raw = commit(
            context,
            canonical_bytes(check),
            "validation_receipt",
            "semflow.native-check/1",
        )
        observed_refs = tuple(
            ArtifactRef.model_validate(value)
            for value in (*check.get("sarif_refs", ()), *check.get("evidence_refs", ()))
        )
        for reference in observed_refs:
            context.artifacts.read(reference)
        status = STATUS.get(check.get("status"), "error")
        subjects = tuple(
            ref for ref in (proposal, patch, source.archive if source else None) if ref
        )
        result.append(
            ValidationReceipt(
                validation_id=uuid5(
                    context.execution_id, f"attempt/{ordinal}/check/{name}"
                ),
                kind=KINDS[name],
                status=status,
                subject_refs=subjects,
                target_refs=targets,
                identity_digest=digest(
                    {
                        "before_tree": context.spec.source.tree_sha256,
                        "subjects": [ref.model_dump(mode="json") for ref in subjects],
                        "check": raw.model_dump(mode="json"),
                    }
                ),
                checks=(
                    CheckResult(
                        check_id=name,
                        category=KINDS[name],
                        status=status,
                        observed=raw,
                        evidence=(raw, *observed_refs),
                        reason=check.get("semantic_limit") or check.get("limitation"),
                    ),
                ),
                tool_profile=context.spec.policy.resource_profile,
                raw_output=raw,
                meaning="Recorded native check only; syntax, model consistency, executed tests and patch acceptance remain separate facts",
            )
        )
    return tuple(result)


def export(context):
    record = context.records.one(RepairRecord, execution_id=context.execution_id)
    targets = tuple(
        context.records.get(Candidate, identifier).source_ref
        for identifier in record.candidate_ids
    )
    if not targets or any(ref is None for ref in targets):
        raise ResearchError(
            "identity_mismatch",
            "Repair output has no exact frozen candidate references",
        )
    directory = context.workspace
    context_path = directory / "repair-context.json"
    semantic = commit(
        context, context_path.read_bytes(), "materials", "semflow.repair-context/1"
    )
    selected = int(record.validation.get("semantic_scope", {}).get("attempts", 0))
    attempts = []
    selected_patch, selected_source, selected_checks = None, None, ()
    for path in sorted(
        (
            path
            for path in directory.glob("attempt-*")
            if path.is_dir() and path.name.removeprefix("attempt-").isdigit()
        ),
        key=lambda path: int(path.name.removeprefix("attempt-")),
    ):
        ordinal = int(path.name.removeprefix("attempt-"))
        proposal = commit(
            context,
            (path / "candidate.json").read_bytes(),
            "materials",
            "semflow.repair-proposal/1",
        )
        patch = (
            commit(
                context,
                (path / "repair.diff").read_bytes(),
                "patch",
                "unified-diff/1",
                "text/x-diff",
            )
            if (path / "repair.diff").is_file()
            else None
        )
        source = (
            capture(
                path / "workspace",
                artifacts=context.artifacts,
                languages=context.spec.source.languages,
                origin={"kind": "directory", "label": f"repair attempt {ordinal}"},
                archive_kind="patched_source",
            )
            if patch
            else None
        )
        raw_checks = (
            json.loads((path / "checks.json").read_text())
            if (path / "checks.json").is_file()
            else {}
        )
        checks = receipts(
            context,
            raw_checks,
            proposal=proposal,
            patch=patch,
            source=source,
            targets=targets,
            ordinal=ordinal,
        )
        engine_receipt = None
        if (
            context.spec.inputs.engine == "openhands"
            and (directory / "openhands-receipt.json").is_file()
        ):
            engine_receipt = ArtifactRef.model_validate_json(
                (directory / "openhands-receipt.json").read_bytes()
            )
        diagnosis = (
            commit(
                context,
                (path / "diagnosis.json").read_bytes(),
                "materials",
                "semflow.repair-diagnostics/1",
            )
            if (path / "diagnosis.json").is_file()
            else None
        )
        attempt_context_path = directory / f"context-before-{ordinal}.json"
        attempt_context = (
            commit(
                context,
                attempt_context_path.read_bytes(),
                "materials",
                "semflow.repair-context/1",
            )
            if attempt_context_path.is_file()
            else semantic
        )
        delivered = ordinal == selected and patch is not None
        attempts.append(
            AttemptRecord(
                attempt_id=uuid5(context.execution_id, f"repair-attempt/{ordinal}"),
                ordinal=ordinal,
                context_digest=attempt_context.sha256,
                context=attempt_context,
                proposal=proposal,
                patch=patch,
                patched_tree_sha256=source.tree_sha256 if source else None,
                patched_source=source,
                checks=checks,
                diagnosis=diagnosis,
                engine_receipt=engine_receipt,
                selected=delivered,
            )
        )
        if delivered:
            selected_patch, selected_source, selected_checks = patch, source, checks
    # WIRE-SEND:research.repair_attempts — peer: read_attempts / ledger.inspect.
    # AGENT: these public hashes cover actual artifact bytes. Native graph state
    # uses its own versioned context/proposal hashes; never substitute one for the other.
    body = RepairAttempts(
        execution_id=context.execution_id,
        snapshot_id=context.spec.source.snapshot_id,
        records=tuple(attempts),
    )
    ref = commit(context, canonical_bytes(body), "repair_attempts", body.schema_version)
    read_attempts(
        context.artifacts,
        ref,
        execution_id=context.execution_id,
        snapshot_id=context.spec.source.snapshot_id,
    )
    outcome = (
        "no_patch"
        if selected_patch is None
        else "checks_passed"
        if selected_checks
        and all(check.status == "passed" for check in selected_checks)
        else "needs_review"
    )
    return RepairResult(
        repair_id=record.id,
        target_refs=targets,
        attempts=ref,
        selected_attempt_id=next(
            (attempt.attempt_id for attempt in attempts if attempt.selected), None
        ),
        patch=selected_patch,
        patched_source=selected_source,
        checks=selected_checks,
        outcome=outcome,
        semantic_context=semantic,
        original_snapshot_unchanged=True,
    )
