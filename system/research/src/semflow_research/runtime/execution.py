"""Common execution receipts; algorithms return typed module results only."""

from dataclasses import dataclass
from datetime import UTC, datetime
from time import monotonic
from typing import get_args
from uuid import UUID

from pydantic import ValidationError
from semflow_contracts.actions import ApprovalRequest
from semflow_contracts.common import digest
from semflow_contracts.errors import Failure, FailureCode, ResearchError
from semflow_contracts.results import (
    Completeness,
    ModuleResult,
    ResultEnvelope,
    Timestamps,
    Usage,
    UsageEntry,
)

from semflow_research.domain.errors import AuditCancelled, ExecutionCancelled
from semflow_research.runtime.calls import CallJournal
from semflow_research.runtime.ledger import input_artifacts


@dataclass(frozen=True)
class KernelOutcome:
    result: ModuleResult
    failure: Failure | None = None
    pending_action: ApprovalRequest | None = None


def usage(context, seconds):
    journal = CallJournal(
        context.executions,
        context.budget_owner_id or context.execution_id,
        context.execution_id,
    )
    records = journal.receipts()
    if context.budget_owner_id and context.budget_owner_id != context.execution_id:
        records = tuple(
            row for row in records if row["execution_id"] == str(context.execution_id)
        )
    receipts = [row["receipt"] or {} for row in records]
    complete = all(
        row["state"] == "known"
        and all(
            type(row["receipt"].get(key)) is int
            for key in ("input_tokens", "output_tokens")
        )
        for row in records
    )
    groups = {}
    for row in records:
        receipt = row["receipt"] or {}
        external = receipt.get("engine") == "openhands"
        provider = (
            "openhands/openai-compatible" if external else context.spec.model.provider
        )
        model = (
            context.spec.inputs.openhands.model
            if external
            else context.spec.model.model
        )
        groups.setdefault((provider, model), []).append(row)
    entries = []
    for (provider, model), rows in groups.items():
        known = all(
            row["state"] == "known"
            and all(
                type((row["receipt"] or {}).get(key)) is int
                for key in ("input_tokens", "output_tokens")
            )
            for row in rows
        )
        entries.append(
            UsageEntry(
                provider=provider,
                model=model,
                call_ids=tuple(UUID(row["call_id"]) for row in rows),
                calls=len(rows),
                input_tokens=sum(row["receipt"]["input_tokens"] for row in rows)
                if known
                else None,
                output_tokens=sum(row["receipt"]["output_tokens"] for row in rows)
                if known
                else None,
                completeness="complete" if known else "partial",
            )
        )
    return Usage(
        calls=len(records),
        input_tokens=sum(row.get("input_tokens") or 0 for row in receipts)
        if complete
        else None,
        output_tokens=sum(row.get("output_tokens") or 0 for row in receipts)
        if complete
        else None,
        wall_seconds=seconds,
        completeness="complete" if complete else "partial",
        by_provider=tuple(entries),
    )


def execute(spec, context, handler, *, resume_command=None):
    if context.execution_id != spec.execution_id or digest(spec) != digest(
        context.spec
    ):
        raise ResearchError(
            "identity_mismatch", "Execution context differs from frozen inputs"
        )
    previous = None
    revision = 0
    if resume_command is not None:
        previous = context.executions.inspect(spec.execution_id)
        revision = context.control.claim_resume(
            resume_command, checkpoint=context.checkpoints.latest
        )
        if revision is None:
            return context.executions.inspect(spec.execution_id)
    elif not context.executions.claim(spec.execution_id):
        previous = context.executions.inspect(spec.execution_id)
        if previous and previous.execution_status in {
            "completed",
            "failed",
            "cancelled",
            "interrupted",
            "awaiting_input",
        }:
            return previous
        raise ResearchError(
            "execution_conflict", "Execution is already running or waiting for input"
        )
    start = monotonic()
    created = datetime.now(UTC)
    status, failure, output, pending = "completed", None, None, None
    completeness = Completeness(status="none")
    failure_artifacts = ()
    try:
        context.control.check_active(spec.execution_id)
        context.execution_records.update(spec.execution_id, status="running")
        outcome = handler(context)
        if isinstance(outcome, KernelOutcome):
            output, failure = outcome.result, outcome.failure
            pending = outcome.pending_action
            status = (
                "failed"
                if failure is not None
                else "awaiting_input"
                if pending
                else "completed"
            )
        else:
            output = outcome
        context.source.verify_snapshot()
        context.control.check_active(spec.execution_id)
        if (
            spec.policy.max_seconds is not None
            and monotonic() - start > spec.policy.max_seconds
        ):
            raise ResearchError(
                "budget_exhausted", "Execution exceeded its frozen wall-time budget"
            )
        coverage = getattr(output, "coverage", None)
        completeness = Completeness(
            status=coverage.status if coverage else "full",
            reasons=coverage.reasons if coverage else (),
        )
    except Exception as exc:  # noqa: BLE001 — publish failures at the execution boundary
        failure_artifacts = getattr(exc, "artifacts", ())
        code = getattr(exc, "code", "internal_error")
        if isinstance(exc, (ExecutionCancelled, AuditCancelled)):
            code, status = "cancelled", "cancelled"
        else:
            status = "failed"
        if isinstance(exc, ValidationError):
            code = "invalid_contract"
        if code not in get_args(FailureCode):
            code = {
                "audit_error": "tool_failed",
                "identity_error": "identity_mismatch",
                "scope_error": "target_not_authorized",
                "scope_violation": "target_not_authorized",
                "candidate_unchanged": "tool_failed",
                "candidate_export_failed": "tool_failed",
                "dependency_environment_unavailable": "tool_unavailable",
                "schema_invalid": "model_output_invalid",
                "provider_error": "model_unavailable",
                "timeout": "tool_failed",
            }.get(code, "internal_error")
        failure = Failure(
            code=code,
            category=failure_category(code),
            message=str(exc) or type(exc).__name__,
            retryable=False,
            phase=context.execution_records.get(spec.execution_id).phase,
            detail=getattr(exc, "detail", None),
        )
        completeness = Completeness(
            status="partial" if output else "none", reasons=(failure.message,)
        )
    ended = datetime.now(UTC)
    # Internal graph state is a working record; the immutable ledger manifest
    # below remains the authority for whether a result was actually published.
    with context.records.transaction() as records:
        from semflow_research.state.models import ExecutionRecord, get_datetime_utc

        record = records.get(ExecutionRecord, spec.execution_id)
        if record.status != status:
            record.status, record.updated_at = status, get_datetime_utc()
            records.save(record)
    # WIRE-SEND:research.result — peer: LocalLedger.publish / inspect and platform projection.
    # AGENT: completion is an execution fact; preserve independent completeness,
    # model assessments and technical checks at the receiver, never infer acceptance.
    result = ResultEnvelope(
        execution_id=spec.execution_id,
        input_digest=digest(spec),
        module=spec.module,
        operation=spec.operation,
        implementation=spec.implementation,
        execution_status=status,
        completeness=completeness,
        result=output,
        failure=failure,
        resources_snapshot=context.resources_snapshot,
        pending_action=pending,
        artifacts=tuple(
            dict.fromkeys(
                (
                    *input_artifacts(output),
                    *input_artifacts(pending),
                    *(
                        (context.resources_snapshot,)
                        if context.resources_snapshot
                        else ()
                    ),
                    *((failure.detail,) if failure and failure.detail else ()),
                    *failure_artifacts,
                )
            )
        ),
        usage=usage(context, monotonic() - start),
        timestamps=Timestamps(
            created_at=previous.timestamps.created_at if previous else created,
            started_at=previous.timestamps.started_at if previous else created,
            ended_at=None if pending else ended,
        ),
    )
    return context.executions.publish(result, expected_revision=revision)


def failure_category(code):
    if code in {
        "cancelled",
        "approval_required",
        "approval_stale",
        "checkpoint_invalid",
        "execution_conflict",
        "external_outcome_unknown",
    }:
        return "control"
    if code in {
        "invalid_contract",
        "unsupported_version",
        "unsupported_operation",
        "target_not_authorized",
    }:
        return "input"
    if code == "identity_mismatch":
        return "identity"
    if code in {"integrity_error", "evidence_invalid"}:
        return "integrity"
    if code in {"tool_failed", "tool_unavailable", "parse_failed"}:
        return "tool"
    if code in {"model_unavailable", "model_output_invalid"}:
        return "model"
    if code in {"budget_exhausted", "resource_exhausted"}:
        return "budget"
    return "internal"
