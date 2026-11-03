"""Bounded review/tool execution and supplementation for one durable candidate batch."""

import json
from copy import deepcopy

from app.adapters.context_packing import fit_navigation
from app.contracts.unified_review import (
    FinalUnifiedReviewResponse,
    UnifiedReviewResponse,
)
from app.domain.audit import AuditCancelled, AuditError
from app.persistence.stage_repository import StageCancelled
from app.services.context_materials import frozen_call, save_json
from app.services.read_tools import observe_tool, reused_read, window_observations
from app.services.review import ReviewService
from app.services.review_feedback import next_feedback, update_attempt
from app.services.review_pool import batch_context
from app.services.unified_review_results import save_batch

SEMANTIC_VERSIONS = frozenset({"8", "9", "10", "11", "12"})
MODERN_VERSIONS = SEMANTIC_VERSIONS | {"5", "6", "7"}


def response_schema(version, final_only):
    if version in {"11", "12"}:
        from app.contracts.review_presentation import (
            FinalPresentedReviewResponse,
            PresentedReviewResponse,
        )

        return FinalPresentedReviewResponse if final_only else PresentedReviewResponse
    if version in SEMANTIC_VERSIONS:
        from app.contracts.discovery_semantics import (
            FinalUnifiedReviewResponseV8,
            UnifiedReviewResponseV8,
        )

        return FinalUnifiedReviewResponseV8 if final_only else UnifiedReviewResponseV8
    return FinalUnifiedReviewResponse if final_only else UnifiedReviewResponse


def gather(service, context, response):
    call = response.tool.model_dump()
    if service.stage.prompt_version in MODERN_VERSIONS:
        from app.services.review_tools import gather_review_tool

        return gather_review_tool(service, context, call)
    previous = reused_read(context, call)
    if previous is not None:
        return observe_tool(context, call, previous, reused=True)
    context = ReviewService.gather(
        service, {"context": context, "response": response.model_dump(mode="json")}
    )["context"]
    data = next(
        r
        for r in context["evidence"]
        if r["id"] == context["tool_trace"][-1]["evidence_id"]
    )
    context["tool_trace"] = context["tool_trace"][:-1]
    context = observe_tool(context, call, data)
    context["source_windows"] = window_observations(
        service.evidence, context["evidence"]
    )
    return context


def call_context(service, context, step, steps):
    version = service.stage.prompt_version
    if version in SEMANTIC_VERSIONS:
        from app.services.discovery_context import (
            refresh_citation_contract,
            refresh_control_context,
        )

        context = refresh_citation_contract(refresh_control_context(service, context))
    # A reused page is an observation; it must not prohibit requesting a different fact.
    final_only = version in MODERN_VERSIONS - {"5"} and step == steps - 1
    context["remaining_model_calls_in_batch"] = steps - step
    context["finalize_required"] = final_only
    context = fit_navigation(context, service.inputs.max_context_chars)
    if len(json.dumps(context, ensure_ascii=False)) > service.inputs.max_context_chars:
        raise AuditError("复核批次必要上下文超过预算", code="context_budget")
    return context, response_schema(version, final_only)


def inspect_batch(service, batch_id, entries, call_limit=None, feedback=None):
    context = batch_context(service, entries)
    if feedback:
        context["server_feedback"] = feedback
    if service.stage.prompt_version in MODERN_VERSIONS:
        from app.services.review_tools import SOURCE_TOOL_CONTRACT

        context["tool_contract"] = SOURCE_TOOL_CONTRACT
    steps = call_limit or service.inputs.max_steps
    saved, base, attempt = None, None, None
    for step in range(steps):
        service.repository.active(service.stage_id)
        try:
            context, schema = call_context(service, context, step, steps)
            call_reference = f"batches/{batch_id}/call-{step}"
            if attempt:
                update_attempt(
                    service, attempt, status="running", call_reference=call_reference
                )
            response = frozen_call(
                service.provider,
                "review",
                context,
                schema,
                service.directory / call_reference,
                limit=getattr(service.provider, "policy", {}).get("max_calls", 24),
                ledger_directory=service.directory,
            )
            service.repository.active(service.stage_id)
            if response.action != "final":
                context = gather(service, context, response)
                continue
            try:
                result = save_batch(
                    service, batch_id, response, context, call_reference=call_reference
                )
            except AuditError as exc:
                if service.stage.prompt_version not in MODERN_VERSIONS or exc.code in {
                    "identity_error",
                    "integrity_error",
                }:
                    raise
                context["server_feedback"] = {
                    "validation_error": str(exc),
                    "instruction": "Correct unsupported verdict/citation; preserve valid assessments and use actual evidence. Unresolved call identity remains insufficient.",
                }
                continue
            saved = result
            save_json(service.directory / "batches" / batch_id / "result.json", result)
            if attempt:
                update_attempt(
                    service,
                    attempt,
                    status="reassessed"
                    if result["revision_accepted_ids"]
                    else "rejected",
                    call_reference=call_reference,
                )
                attempt = None
            if base is None:
                base = deepcopy(context)
            followup = next_feedback(service, batch_id, result, base, steps - step - 1)
            if followup is None:
                return result
            context, attempt = followup
        except StageCancelled, AuditCancelled:
            raise
        except Exception as exc:
            code = getattr(exc, "code", "verification_failed")
            if (
                not attempt
                or saved is None
                or code in {"identity_error", "integrity_error"}
            ):
                raise
            update_attempt(
                service, attempt, status="incomplete", code=code, reason=str(exc)[:500]
            )
            # Optional supplementation never turns an accepted uncertain verdict into no assessment.
            return {**saved, "feedback_stop_code": code}
    if attempt and saved is not None:
        update_attempt(
            service,
            attempt,
            status="incomplete",
            code="unit_budget",
            reason="原批次剩余步数耗尽，保留初评及未决状态",
        )
        return {**saved, "feedback_stop_code": "unit_budget"}
    raise AuditError(
        "复核批次步数耗尽，结论仍未决: "
        + str(context.get("server_feedback", ""))[:500],
        code="unit_budget",
    )
