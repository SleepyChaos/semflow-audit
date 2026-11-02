"""Batched source verification of CodeQL alerts and independent scout hypotheses."""

from app.adapters.artifacts import ArtifactStore
from app.domain.audit import AuditCancelled, AuditError
from app.persistence.stage_repository import StageCancelled
from app.services.context_materials import (
    digest,
    save_json,
    verify_snapshot,
)
from app.services.review_pool import (
    batches,
    fit_batches,
    pool_for_resume,
)


class UnifiedReview:
    def __init__(self, service):
        self.stage_id, self.stage = service.stage_id, service.stage
        self.repository, self.provider = service.repository, service.provider
        self.evidence, self.inputs = service.evidence, service.inputs
        self.directory = ArtifactStore().directory(self.stage_id)

    def prepare(self, _):
        from app.services.review_feedback import initialize_feedback

        initialize_feedback(self)
        pool = pool_for_resume(self)
        self.repository.update(
            self.stage_id, phase="verify_candidate_batches", model=self.provider.model
        )
        return {"pool_hash": digest(pool)}

    def inspect_batch(self, batch_id, entries, call_limit=None, feedback=None):
        from app.services.review_batch import inspect_batch

        return inspect_batch(self, batch_id, entries, call_limit, feedback)

    def verify(self, state):
        pool = pool_for_resume(self)
        if digest(pool) != state["pool_hash"]:
            raise AuditError("复核候选池身份已变化")
        schedule = batches(
            pool,
            self.inputs.batch_size,
            self.stage.prompt_version in {"5", "6", "7", "8", "9", "10", "11", "12"},
            coherent_conditions=self.stage.prompt_version in {"9", "10", "11", "12"},
        )
        schedule = fit_batches(self, schedule)
        if self.inputs.max_batches:
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
                    "remaining_reason": "explicit scope, provider interruption or lack of progress; unprocessed candidates are unknown",
                },
            },
        )
        stop_reason = None
        for index, entries in enumerate(schedule):
            batch_id = digest(entries)[:24]
            current = self.repository.get(self.stage_id).result
            if batch_id in {r["batch_id"] for r in current.get("batches", [])}:
                continue
            try:
                maximum = getattr(self.provider, "policy", {}).get("max_calls", 24)
                available = maximum - self.provider.usage.get("calls", 0)
                call_limit = (
                    self.inputs.max_steps
                    if maximum == 0
                    else max(
                        1,
                        min(
                            self.inputs.max_steps, available // (len(schedule) - index)
                        ),
                    )
                    if self.stage.prompt_version
                    in {"6", "7", "8", "9", "10", "11", "12"}
                    else None
                )
                result = self.inspect_batch(batch_id, entries, call_limit)
                save_json(self.directory / "batches" / batch_id / "result.json", result)
                if result.get("feedback_stop_code") in {
                    "budget_exhausted",
                    "timeout",
                    "provider_error",
                    "rate_limited",
                }:
                    stop_reason = result["feedback_stop_code"]
                    break
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
                if code in {
                    "budget_exhausted",
                    "timeout",
                    "provider_error",
                    "rate_limited",
                }:
                    stop_reason = code
                    break
            from app.adapters.ai.policy import stalled

            if stalled(
                self.repository.get(self.stage_id).result.get("batches", []),
                getattr(self.provider, "policy", {}),
            ):
                stop_reason = "no_progress"
                break
        self.repository.update(
            self.stage_id,
            result={
                **self.repository.get(self.stage_id).result,
                "stop_reason": stop_reason,
            },
        )
        if self.stage.prompt_version in {"8", "9", "10", "11", "12"}:
            from app.services.review_recovery import recover_unreviewed

            if not stop_reason:
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
            "summary": f"已复核 {len(reviewed)} 项，仍有 {len(uncovered)} 项未完成；采用 AI 分类，可人工调整。"
            if self.stage.prompt_version == "12"
            else f"Reviewed {len(reviewed)} candidate recommendations; {len(uncovered)} candidates remain unreviewed. Human confirmation required.",
            "classification_mode": "automatic_with_human_override"
            if self.stage.prompt_version == "12"
            else "human_confirmation",
            "coverage_status": "partial" if uncovered else "completed",
            "snapshot_hash": self.evidence.audit.snapshot_hash,
        }
        save_json(self.directory / "unified-review-result.json", final)
        self.repository.update(
            self.stage_id,
            status="completed",
            phase="classifications_ready"
            if self.stage.prompt_version == "12"
            else "awaiting_human_decisions",
            result=final,
            usage=self.provider.usage,
        )
        return {"saved": True}
