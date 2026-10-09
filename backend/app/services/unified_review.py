"""Batched source verification of CodeQL alerts and independent scout hypotheses."""

import json

from app.adapters.artifacts import ArtifactStore
from app.contracts.unified_review import (
    FinalUnifiedReviewResponse,
    UnifiedReviewResponse,
)
from app.domain.audit import AuditCancelled, AuditError
from app.persistence.stage_repository import StageCancelled
from app.services.context_materials import (
    digest,
    frozen_call,
    save_json,
    verify_snapshot,
)
from app.services.read_tools import observe_tool, reused_read, window_observations
from app.services.review import ReviewService
from app.services.review_pool import batch_context, batches, pool_for_resume
from app.services.unified_review_results import save_batch


class UnifiedReview:
    def __init__(self, service):
        self.stage_id, self.stage = service.stage_id, service.stage
        self.repository, self.provider = service.repository, service.provider
        self.evidence, self.inputs = service.evidence, service.inputs
        self.directory = ArtifactStore().directory(self.stage_id)

    def prepare(self, _):
        pool = pool_for_resume(self)
        self.repository.update(
            self.stage_id, phase="verify_candidate_batches", model=self.provider.model
        )
        return {"pool_hash": digest(pool)}

    def inspect_batch(self, batch_id, entries, call_limit=None, feedback=None):
        context = batch_context(self, entries)
        if feedback:
            context["server_feedback"] = feedback
        modern = self.stage.prompt_version in {"5", "6", "7", "8", "9", "10"}
        if modern:
            from app.services.review_tools import SOURCE_TOOL_CONTRACT

            context["tool_contract"] = SOURCE_TOOL_CONTRACT
        steps = call_limit or self.inputs.max_steps
        for step in range(steps):
            self.repository.active(self.stage_id)
            if self.stage.prompt_version in {"8", "9", "10"}:
                from app.services.discovery_context import (
                    refresh_citation_contract,
                    refresh_control_context,
                )

                context = refresh_citation_contract(
                    refresh_control_context(self, context)
                )
            if (
                len(json.dumps(context, ensure_ascii=False))
                > self.inputs.max_context_chars
            ):
                raise AuditError("复核批次必要上下文超过预算", code="context_budget")
            final_only = self.stage.prompt_version in {"6", "7", "8", "9", "10"} and (
                step == steps - 1
                or any(r.get("reused") for r in context.get("tool_trace", []))
            )
            context["remaining_model_calls_in_batch"] = steps - step
            context["finalize_required"] = final_only
            schema = FinalUnifiedReviewResponse if final_only else UnifiedReviewResponse
            if self.stage.prompt_version in {"8", "9", "10"}:
                from app.contracts.discovery_semantics import (
                    FinalUnifiedReviewResponseV8,
                    UnifiedReviewResponseV8,
                )

                schema = (
                    FinalUnifiedReviewResponseV8
                    if final_only
                    else UnifiedReviewResponseV8
                )
            response = frozen_call(
                self.provider,
                "review",
                context,
                schema,
                self.directory / "batches" / batch_id / f"call-{step}",
                limit=getattr(self.provider, "policy", {}).get("max_calls", 24),
                ledger_directory=self.directory,
            )
            self.repository.active(self.stage_id)
            if response.action == "final":
                try:
                    return save_batch(self, batch_id, response, context)
                except AuditError as exc:
                    if not modern or exc.code in {"identity_error", "integrity_error"}:
                        raise
                    context["server_feedback"] = {
                        "validation_error": str(exc),
                        "instruction": "Correct unsupported verdict/citation; preserve valid assessments and use actual evidence. Unresolved call identity is insufficient, not a supported dangerous operation.",
                    }
                    continue
            call = response.tool.model_dump()
            if modern:
                from app.services.review_tools import gather_review_tool

                context = gather_review_tool(self, context, call)
                continue
            previous = reused_read(context, call)
            if previous is not None:
                context = observe_tool(context, call, previous, reused=True)
                continue
            # Existing scope/knowledge/published-query validation stays in one dispatcher.
            context = ReviewService.gather(
                self, {"context": context, "response": response.model_dump(mode="json")}
            )["context"]
            data = next(
                r
                for r in context["evidence"]
                if r["id"] == context["tool_trace"][-1]["evidence_id"]
            )
            # gather already appended the actual execution trace; add observation once.
            context["tool_trace"] = context["tool_trace"][:-1]
            context = observe_tool(context, call, data)
            context["source_windows"] = window_observations(
                self.evidence, context["evidence"]
            )
        raise AuditError(
            "复核批次步数耗尽，结论仍未决: "
            + str(context.get("server_feedback", ""))[:500],
            code="unit_budget",
        )

    def verify(self, state):
        pool = pool_for_resume(self)
        if digest(pool) != state["pool_hash"]:
            raise AuditError("复核候选池身份已变化")
        schedule = batches(
            pool,
            self.inputs.batch_size,
            self.stage.prompt_version in {"5", "6", "7", "8", "9", "10"},
            coherent_conditions=self.stage.prompt_version in {"9", "10"},
        )
        schedule = schedule[: self.inputs.max_batches]
        self.repository.update(
            self.stage_id,
            result={
                **self.repository.get(self.stage_id).result,
                "schedule": {
                    "candidate_count": len(pool["entries"]),
                    "scheduled_candidates": sum(map(len, schedule)),
                    "batch_limit": self.inputs.max_batches,
                    "scheduled_batches": len(schedule),
                    "remaining_reason": "explicit batch/call/time budgets; unprocessed candidates are unknown",
                },
            },
        )
        for index, entries in enumerate(schedule):
            batch_id = digest(entries)[:24]
            current = self.repository.get(self.stage_id).result
            if batch_id in {r["batch_id"] for r in current.get("batches", [])}:
                continue
            try:
                available = getattr(self.provider, "policy", {}).get(
                    "max_calls", 24
                ) - self.provider.usage.get("calls", 0)
                call_limit = (
                    max(
                        1,
                        min(
                            self.inputs.max_steps, available // (len(schedule) - index)
                        ),
                    )
                    if self.stage.prompt_version in {"6", "7", "8", "9", "10"}
                    else None
                )
                result = self.inspect_batch(batch_id, entries, call_limit)
                save_json(self.directory / "batches" / batch_id / "result.json", result)
            except StageCancelled, AuditCancelled:
                raise
            except Exception as exc:
                # gather() may have persisted trace since current was read; preserve its latest data.
                current = self.repository.get(self.stage_id).result
                code = getattr(exc, "code", "verification_failed")
                if code in {"identity_error", "integrity_error"}:
                    raise
                failed = {
                    "batch_id": batch_id,
                    "status": "incomplete",
                    "reason": str(exc)[:500],
                    "code": code,
                    "candidate_ids": [r["candidate_id"] for r in entries],
                    "unreviewed_candidate_ids": [r["candidate_id"] for r in entries],
                }
                self.repository.update(
                    self.stage_id,
                    result={
                        **current,
                        "batches": [*current.get("batches", []), failed],
                    },
                )
                if code in {"budget_exhausted", "timeout", "provider_error"}:
                    break
        if self.stage.prompt_version in {"8", "9", "10"}:
            from app.services.review_recovery import recover_unreviewed

            recover_unreviewed(self, schedule)
        return {}

    def finalize(self, state):
        self.repository.active(self.stage_id)
        verify_snapshot(self.evidence)
        pool = pool_for_resume(self)
        if digest(pool) != state["pool_hash"]:
            raise AuditError("复核候选池身份已变化")
        result = self.repository.get(self.stage_id).result
        completed = [
            b
            for b in result.get("batches", [])
            if b["status"] in {"completed", "partial"}
        ]
        recommendations = [r for b in completed for r in b["recommendations"]]
        reviewed = {r["id"] for r in recommendations}
        uncovered = [
            r["candidate_id"]
            for r in pool["entries"]
            if r["candidate_id"] not in reviewed
        ]
        final = {
            **result,
            "schema_version": self.stage.prompt_version,
            "candidate_ids": list(
                dict.fromkeys(
                    [r["candidate_id"] for r in pool["entries"]]
                    + [r["id"] for r in recommendations]
                )
            ),
            "recommendations": recommendations,
            "unreviewed_candidate_ids": uncovered,
            "root_relations": [
                r for b in completed for r in b.get("root_relations", [])
            ],
            "root_relation_limit": "Within reviewed cohorts only; no automatic merge, exclusion, novelty or count change",
            "reviewed_static_finding_ids": [
                r["static_alert"]["id"]
                for r in pool["entries"]
                if r["origin"] == "static" and r["candidate_id"] in reviewed
            ],
            "unreviewed_static_finding_ids": [
                r["id"]
                for r in self.evidence.audit.findings
                if r["id"]
                not in {
                    e["static_alert"]["id"]
                    for e in pool["entries"]
                    if e["origin"] == "static" and e["candidate_id"] in reviewed
                }
            ],
            "summary": f"Reviewed {len(reviewed)} candidate recommendations; {len(uncovered)} candidates remain unreviewed. Human confirmation required.",
            "coverage_status": "partial" if uncovered else "completed",
            "snapshot_hash": self.evidence.audit.snapshot_hash,
        }
        save_json(self.directory / "unified-review-result.json", final)
        self.repository.update(
            self.stage_id,
            status="completed",
            phase="awaiting_human_decisions",
            result=final,
            usage=self.provider.usage,
        )
        return {"saved": True}
