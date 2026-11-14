"""Run independent scan/scout branches, then review their explicit frozen outputs."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime

from semflow_contracts.common import digest
from semflow_contracts.errors import Failure, ResearchError
from semflow_contracts.results import (
    BranchOutcome,
    Completeness,
    ResultEnvelope,
    Timestamps,
    Usage,
)
from semflow_contracts.runs import validate_spec

from semflow_research.runtime.children import bind_child, child_id
from semflow_research.runtime.discovery_merge import merge, source_indexes
from semflow_research.runtime.execution import KernelOutcome, failure_category
from semflow_research.runtime.factory import assemble


def child_spec(parent, role, inputs, version):
    # WIRE-SEND:research.run — peer: factory.assemble / public.discovery.execute.
    # AGENT: child method and Prompt versions differ; copy source/resources/policy
    # exactly, freeze role inputs and bind a new execution to the shared parent.
    value = parent.model_dump(mode="json")
    value.update(
        execution_id=str(child_id(parent.execution_id, role)),
        operation=role,
        inputs=inputs,
    )
    if role == "scan":
        value.update(model=None, prompts=[])
    value["lineage"].update(parent_execution_id=str(parent.execution_id), retry_of=None)
    value["implementation"].update(
        method_id=parent.implementation.method_id + "/" + role, method_version=version
    )
    return validate_spec(value)


def prepare_failure(context, spec, exc):
    """An initialization failure is an explicit failed branch, with its own ID."""
    code = getattr(exc, "code", "internal_error")
    from typing import get_args

    from semflow_contracts.errors import FailureCode

    code = code if code in get_args(FailureCode) else "internal_error"
    failure = Failure(
        code=code,
        category=failure_category(code),
        message=str(exc) or type(exc).__name__,
        retryable=False,
        phase="prepare_child",
    )
    previous = context.executions.inspect(spec.execution_id)
    if previous:
        return previous
    with context.executions._connect() as db:
        state = context.executions._row(db, spec.execution_id)["status"]
    if state != "created":
        return BranchOutcome(
            branch=spec.operation,
            execution_id=spec.execution_id,
            status="interrupted",
            failure=failure,
        )
    now = datetime.now(UTC)
    return context.executions.publish(
        ResultEnvelope(
            execution_id=spec.execution_id,
            input_digest=digest(spec),
            module="discovery",
            operation=spec.operation,
            implementation=spec.implementation,
            execution_status="failed",
            result=None,
            failure=failure,
            completeness=Completeness(status="none", reasons=(failure.message,)),
            usage=Usage(
                calls=0,
                input_tokens=0,
                output_tokens=0,
                wall_seconds=0,
                completeness="complete",
            ),
            timestamps=Timestamps(created_at=now, ended_at=now),
        ),
        expected_revision=0,
    )


def run_child(context, spec, role):
    bind_child(context.executions, context.spec, spec, role)
    try:
        kernel = assemble(
            spec,
            root=context.root,
            settings=context.settings,
            budget_owner_id=context.execution_id,
            model=context.model,
            control_guard=getattr(context.control, "guard", None),
        )
        if spec.model is not None and context.model is not None:
            if not hasattr(context.model, "for_execution"):
                raise ResearchError(
                    "invalid_contract",
                    "Dual discovery model injection must bind a separate provider to each child execution",
                )
            kernel = replace(kernel, model=context.model.for_execution(kernel))
        from semflow_research.public.discovery import execute

        return execute(spec, kernel)
    except Exception as exc:  # noqa: BLE001 — preserve a branch initialization failure
        return prepare_failure(context, spec, exc)


def branch_of(result):
    if isinstance(result, BranchOutcome):
        return result
    return BranchOutcome(
        branch=result.operation,
        execution_id=result.execution_id,
        status=result.execution_status,
        result_manifest=result.manifest,
        failure=result.failure,
    )


def discover(context):
    parent = context.spec
    if parent.implementation.method_version != "1":
        raise ResearchError(
            "unsupported_version", "Unknown dual discovery orchestrator method"
        )
    enabled = [
        role for role in ("scan", "scout") if getattr(parent.inputs, role) is not None
    ]
    specs = {
        role: child_spec(
            parent,
            role,
            getattr(parent.inputs, role).model_dump(mode="json"),
            parent.inputs.scout_method_version if role == "scout" else "1",
        )
        for role in enabled
    }
    # Both requests are frozen before either branch starts. Scout owns a separate
    # source/record namespace, so it cannot inspect CodeQL findings or artifacts.
    with ThreadPoolExecutor(max_workers=len(specs)) as pool:
        jobs = {
            role: pool.submit(run_child, context, spec, role)
            for role, spec in specs.items()
        }
        returned = [jobs[role].result() for role in enabled]
    results = [result for result in returned if isinstance(result, ResultEnvelope)]
    branches = [branch_of(result) for result in returned]
    context, candidates, evidence = source_indexes(context, results)
    review = None
    if parent.inputs.review is not None and any(
        result.result is not None for result in results
    ):
        producers = sorted(
            {result.execution_id for result in results if result.result is not None},
            key=str,
        )
        spec = child_spec(
            parent,
            "review",
            {
                "baseline": next(
                    (
                        row.result.baseline.model_dump(mode="json")
                        for row in results
                        if row.operation == "scan"
                        and row.result
                        and row.result.baseline
                    ),
                    None,
                ),
                "targets": candidates.model_dump(mode="json"),
                "evidence": evidence.model_dump(mode="json"),
                "source_execution_ids": list(map(str, producers)),
                "policy": parent.inputs.review.model_dump(mode="json"),
            },
            parent.inputs.review_method_version,
        )
        returned_review = run_child(context, spec, "review")
        branches.append(branch_of(returned_review))
        if isinstance(returned_review, ResultEnvelope):
            results.append(returned_review)
            review = returned_review
    output = merge(
        context,
        results,
        branches,
        source_candidates=candidates,
        source_evidence=evidence,
        review_result=review,
    )
    failed = [
        branch
        for branch in branches
        if branch.status != "completed"
        and (
            branch.branch in parent.inputs.required_branches
            or branch.branch == "review"
        )
    ]
    failure = failed[0].failure if failed else None
    if failed and failure is None:
        failure = Failure(
            code="tool_failed",
            category="tool",
            message="Required discovery branch did not complete",
            retryable=False,
            phase=failed[0].branch,
        )
    return KernelOutcome(result=output, failure=failure)
