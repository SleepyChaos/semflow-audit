"""Algorithm extracted from app.services.unified_review.

Runtime dependencies are passed explicitly; no platform ORM or configuration.
Changes to JSON require checking the corresponding semflow_contracts/wire peer.

Batched source verification of CodeQL alerts and independent scout hypotheses."""

from semflow_research.adapters.artifacts import ArtifactStore
from semflow_research.discovery.review_pool import batches, fit_batches, pool_for_resume
from semflow_research.domain.errors import (
    AuditCancelled,
    AuditError,
    ExecutionCancelled,
)
from semflow_research.evidence.context_materials import (
    digest,
    save_json,
    verify_snapshot,
)


class UnifiedReview:
    def __init__(self, service, *, _kernel):
        self._kernel = _kernel
        self.execution_id, self.execution = (service.execution_id, service.execution)
        self.repository, self.provider = (service.repository, service.provider)
        self.evidence, self.inputs = (service.evidence, service.inputs)
        self.continuation = getattr(service, "continuation", None)
        self.directory = ArtifactStore(_kernel=_kernel).directory(self.execution_id)

    def prepare(self, _):
        _kernel = self._kernel
        from semflow_research.discovery.review_feedback import initialize_feedback

        initialize_feedback(self)
        pool = pool_for_resume(self, _kernel=_kernel)
        self.repository.update(
            self.execution_id,
            phase="verify_candidate_batches",
            model=self.provider.model,
        )
        return {"pool_hash": digest(pool)}

    def inspect_batch(self, batch_id, entries, call_limit=None, feedback=None):
        _kernel = self._kernel
        from semflow_research.discovery.review_batch import inspect_batch

        return inspect_batch(
            self, batch_id, entries, call_limit, feedback, _kernel=_kernel
        )

    def record_progress(self, batch_id, entries, state, code=None):
        current = self.repository.get(self.execution_id).result
        events = current.get("review_progress", [])
        event = {
            "batch_id": batch_id,
            "candidate_ids": [entry["candidate_id"] for entry in entries],
            "state": state,
            **({"code": code} if code else {}),
        }
        if event not in events:
            self.repository.update(
                self.execution_id,
                result={**current, "review_progress": [*events, event]},
            )

    def verify(self, state):
        _kernel = self._kernel
        pool = pool_for_resume(self, _kernel=_kernel)
        if digest(pool) != state["pool_hash"]:
            raise AuditError("复核候选池身份已变化")
        scheduler = _kernel.spec.inputs.policy.scheduler
        evidence_mode = scheduler == "evidence_v3"
        source_balanced = scheduler is not None
        frontier = None
        if scheduler in {"clustered_v2", "evidence_v3"}:
            from semflow_research.discovery.review_scheduling import (
                cluster_frontier,
                evidence_frontier,
            )

            planner = evidence_frontier if evidence_mode else cluster_frontier
            frontier = planner(pool["entries"])
        size = 1 if evidence_mode else self.inputs.batch_size
        schedule = (
            [
                list(frontier.ranked[i : i + size])
                for i in range(0, len(frontier.ranked), size)
            ]
            if frontier
            else batches(
                pool,
                self.inputs.batch_size,
                self.execution.method_version
                in {"5", "6", "7", "8", "9", "10", "11", "12"},
                coherent_conditions=self.execution.method_version
                in {"9", "10", "11", "12"},
                source_balanced=source_balanced,
            )
        )
        ranked = [entry for batch in schedule for entry in batch]
        schedule = fit_batches(
            self,
            schedule,
            _kernel=_kernel,
            limit=self.inputs.max_batches if source_balanced else 0,
        )
        if self.inputs.max_batches:
            schedule = schedule[: self.inputs.max_batches]
        selected = {entry["candidate_id"] for batch in schedule for entry in batch}
        decisions = []
        if source_balanced:
            from semflow_research.discovery.review_scheduling import (
                cross_source_peers,
                score_entry,
            )

            peers = cross_source_peers(pool["entries"])
            for rank, entry in enumerate(ranked, 1):
                identifier = entry["candidate_id"]
                related = sorted(peers.get(identifier, ()))
                priority, reason = score_entry(entry, bool(related))
                decisions.append(
                    {
                        "candidate_id": identifier,
                        "origin": entry["origin"],
                        "rank": rank,
                        "priority": priority,
                        "priority_reason": reason,
                        "cross_source_peers": related,
                        **(
                            {
                                "original_rank": frontier.previous_ranks[identifier],
                                "cluster_members": list(frontier.clusters[identifier]),
                            }
                            if frontier
                            else {}
                        ),
                        "disposition": "scheduled"
                        if identifier in selected
                        else "outside_batch_limit",
                    }
                )
        if evidence_mode:
            decisions.extend(
                {
                    "candidate_id": entry["candidate_id"],
                    "original_rank": frontier.previous_ranks[entry["candidate_id"]],
                    "rank": None,
                    "disposition": entry["source_unavailable"],
                }
                for entry in pool["entries"]
                if entry.get("source_unavailable")
            )
        if frontier:
            for representative, members in frontier.clusters.items():
                for identifier in members[1:]:
                    decisions.append(
                        {
                            "candidate_id": identifier,
                            "original_rank": frontier.previous_ranks[identifier],
                            "rank": None,
                            "representation": representative,
                            "disposition": "exact_static_duplicate",
                        }
                    )
        self.repository.update(
            self.execution_id,
            result={
                **self.repository.get(self.execution_id).result,
                "schedule": {
                    "candidate_count": len(pool["entries"]),
                    "scheduled_candidates": sum(map(len, schedule)),
                    "candidate_ids": [
                        entry["candidate_id"] for batch in schedule for entry in batch
                    ],
                    "batch_limit": self.inputs.max_batches,
                    "scheduled_batches": len(schedule),
                    **(
                        {"scheduler": scheduler, "decisions": decisions}
                        if source_balanced
                        else {}
                    ),
                    "remaining_reason": "explicit scope, provider interruption or lack of progress; unprocessed candidates are unknown",
                },
            },
        )
        stop_reason = None
        for index, entries in enumerate(schedule):
            batch_id = digest(entries)[:24]
            current = self.repository.get(self.execution_id).result
            if batch_id in {r["batch_id"] for r in current.get("batches", [])}:
                continue
            if evidence_mode:
                self.record_progress(batch_id, entries, "reviewing")
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
                    if self.execution.method_version
                    in {"6", "7", "8", "9", "10", "11", "12"}
                    else None
                )
                result = self.inspect_batch(batch_id, entries, call_limit)
                save_json(self.directory / "batches" / batch_id / "result.json", result)
                if evidence_mode:
                    self.record_progress(
                        batch_id,
                        entries,
                        result["status"],
                        result.get("feedback_stop_code"),
                    )
                if result.get("feedback_stop_code") in {
                    "budget_exhausted",
                    "timeout",
                    "provider_error",
                    "rate_limited",
                }:
                    stop_reason = result["feedback_stop_code"]
                    break
            except (ExecutionCancelled, AuditCancelled):
                raise
            except Exception as exc:
                current = self.repository.get(self.execution_id).result
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
                    self.execution_id,
                    result={
                        **current,
                        "batches": [*current.get("batches", []), failed],
                    },
                )
                if evidence_mode:
                    self.record_progress(batch_id, entries, "execution_failed", code)
                if code in {
                    "budget_exhausted",
                    "timeout",
                    "provider_error",
                    "rate_limited",
                }:
                    stop_reason = code
                    break
            from semflow_research.adapters.ai.policy import stalled

            if stalled(
                self.repository.get(self.execution_id).result.get("batches", []),
                getattr(self.provider, "policy", {}),
            ):
                stop_reason = "no_progress"
                break
        self.repository.update(
            self.execution_id,
            result={
                **self.repository.get(self.execution_id).result,
                "stop_reason": stop_reason,
            },
        )
        if self.execution.method_version in {"8", "9", "10", "11", "12"}:
            from semflow_research.discovery.review_recovery import recover_unreviewed

            if not stop_reason and not evidence_mode:
                recover_unreviewed(self, schedule)
        return {}

    def finalize(self, state):
        _kernel = self._kernel
        self.repository.active(self.execution_id)
        verify_snapshot(self.evidence)
        pool = pool_for_resume(self, _kernel=_kernel)
        if digest(pool) != state["pool_hash"]:
            raise AuditError("复核候选池身份已变化")
        result = self.repository.get(self.execution_id).result
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
            "schema_version": self.execution.method_version,
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
                for r in self.evidence.source_context.findings
                if r["id"]
                not in {
                    e["static_alert"]["id"]
                    for e in pool["entries"]
                    if e["origin"] == "static" and e["candidate_id"] in reviewed
                }
            ],
            "summary": f"Reviewed {len(reviewed)} candidate recommendations; {len(uncovered)} candidates remain unreviewed. Human confirmation required.",
            "classification_mode": "human_confirmation",
            "coverage_status": "partial" if uncovered else "completed",
            "snapshot_hash": self.evidence.source_context.snapshot_hash,
        }
        if _kernel.spec.inputs.policy.scheduler == "evidence_v3":
            final["schedule"] = {
                **final.get("schedule", {}),
                "events": result.get("review_progress", []),
            }
        from semflow_research.discovery.review_handoff import candidate_handoffs

        # Peer: discovery_outputs exports this diagnostic field through DiscoveryTrace.
        # Modern review has structured premise roles. Older executors keep their
        # original handoff behavior and can still read historical trace records.
        guidance = (
            {"directory": self.directory, "evidence": self.evidence}
            if int(self.execution.method_version) >= 8
            else {}
        )
        final["candidate_handoffs"] = candidate_handoffs(
            pool["entries"], final, **guidance
        )
        if _kernel.spec.inputs.policy.scheduler:
            from collections import Counter

            states = Counter(row["reason_code"] for row in final["candidate_handoffs"])
            final["coverage"] = {
                "status": "partial" if uncovered else "completed",
                "scheduled_candidates": result.get("schedule", {}).get(
                    "scheduled_candidates", 0
                ),
                "accepted_assessments": len(reviewed),
                "reason_codes": sorted(
                    reason
                    for reason, count in states.items()
                    if reason and reason != "assessment_accepted" and count
                ),
                "candidate_states": dict(states),
                "stop_reason": result.get("stop_reason"),
            }
        save_json(self.directory / "unified-review-result.json", final)
        self.repository.update(
            self.execution_id,
            status="completed",
            phase="awaiting_human_decisions",
            result=final,
            usage=self.provider.usage,
        )
        return {"saved": True}
