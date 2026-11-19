"""Algorithm extracted from app.services.review_feedback.

Runtime dependencies are passed explicitly; no platform ORM or configuration.
Changes to JSON require checking the corresponding semflow_contracts/wire peer.
"""

"""Durable, candidate-specific supplementation inside the original batch allowance."""
import hashlib
from copy import deepcopy
from itertools import islice
from pathlib import Path

from semflow_research.adapters.context_packing import context_size, fit_navigation
from semflow_research.adapters.review_evidence import missing_source_paths, source_pages
from semflow_research.adapters.snapshot import snapshot_digest
from semflow_research.discovery.discovery_context import (
    refresh_citation_contract,
    refresh_control_context,
)
from semflow_research.domain.errors import (
    AuditCancelled,
    AuditError,
    ExecutionCancelled,
)
from semflow_research.evidence.context_materials import digest, save_json
from semflow_research.evidence.read_tools import window_observations


def initialize_feedback(service):
    current = service.repository.get(service.execution_id).result
    if "review_feedback_policy" in current:
        return
    prompt = (
        Path(__file__).resolve().parents[1] / "prompts/review-feedback.v1.txt"
    ).read_text()
    from semflow_research.discovery.review_gap_planner import navigation_enabled

    navigation = navigation_enabled(service._kernel)
    if navigation:
        prompt += "\nUse evidence_gaps to name remaining local symbols and separate runtime and external needs."
    policy = {
        "version": "2" if navigation else "1",
        "enabled": not current.get("pool")
        and service.execution.method_version in {"8", "9", "10", "11", "12"}
        and service.inputs.supplement_insufficient,
        "max_rounds_per_candidate": 3 if navigation else 1,
        "max_source_pages": 3,
        "model_allowance": "remaining_original_batch_steps_and_shared_provider_budget",
        "prompt": prompt,
        "prompt_hash": hashlib.sha256(prompt.encode()).hexdigest(),
    }
    service.repository.update(
        service.execution_id, result={**current, "review_feedback_policy": policy}
    )


def update_attempt(service, identifier, **values):
    current = service.repository.get(service.execution_id).result
    attempts = [
        {**r, **values} if r["id"] == identifier else r
        for r in current.get("review_feedback_attempts", [])
    ]
    service.repository.update(
        service.execution_id, result={**current, "review_feedback_attempts": attempts}
    )
    row = next(r for r in attempts if r["id"] == identifier)
    save_json(service.directory / "feedback" / identifier / "attempt.json", row)


def _begin_attempt(service, batch_id, assessment, remaining, round_number=None):
    current = service.repository.get(service.execution_id).result
    identity = [batch_id, assessment["candidate_id"], "feedback-v1"]
    if round_number is not None:
        identity = [batch_id, assessment["candidate_id"], "feedback-v2", round_number]
    identifier = digest(identity)[:24]
    row = {
        "id": identifier,
        "batch_id": batch_id,
        "candidate_ids": [assessment["candidate_id"]],
        "status": "started",
        "remaining_batch_calls": remaining,
        "missing_premises": assessment.get("missing_premises", []),
        "missing_roles": [
            p["premise"]
            for p in assessment.get("premises", [])
            if p["status"] == "missing"
        ],
        "source_events": [],
    }
    if round_number is not None:
        row.update(round=round_number, snapshot_id=str(service.execution.snapshot_id))
    service.repository.update(
        service.execution_id,
        result={
            **current,
            "review_feedback_attempts": [
                *current.get("review_feedback_attempts", []),
                row,
            ],
        },
    )
    update_attempt(service, identifier)
    return identifier


def _target_context(base, assessment, batch_id, policy):
    context = deepcopy(base)
    identifier = assessment["candidate_id"]
    context["targets"] = [
        t for t in context["targets"] if t["candidate_id"] == identifier
    ]
    context["allow_supplementary_findings"] = False
    context["feedback_revision"] = {"batch_id": batch_id, "candidate_ids": [identifier]}
    context["server_feedback"] = {
        "version": policy["version"],
        "instruction": policy["prompt"],
        "missing_premises": assessment.get("missing_premises", []),
        "missing_roles": [
            p["premise"]
            for p in assessment.get("premises", [])
            if p["status"] == "missing"
        ],
    }
    return refresh_citation_contract(context)


def _pack(context, maximum):
    context = fit_navigation(context, maximum - 384)
    if context_size(context) > maximum - 384:
        raise AuditError("补证上下文超过预算；原结论保持未决", code="context_budget")
    return context


def _supply_pages(service, context, files, policy, *, _kernel):
    maximum = service.inputs.max_context_chars
    context = _pack(context, maximum)
    events, consumed = ([], 0)
    for file in files:
        if consumed >= policy["max_source_pages"]:
            events.append({"file": file, "status": "page_budget"})
            continue
        try:
            service.evidence.allowed(file)
            offered = False
            for page, origin in islice(
                source_pages(
                    service.evidence, file, context["evidence"], _kernel=_kernel
                ),
                policy["max_source_pages"] - consumed,
            ):
                service.repository.active(service.execution_id)
                offered, consumed = (True, consumed + 1)
                proposal = {**context, "evidence": [*context["evidence"], page]}
                proposal["source_windows"] = window_observations(
                    service.evidence, proposal["evidence"]
                )
                try:
                    context = _pack(proposal, maximum)
                except AuditError:
                    events.append(
                        {
                            "file": file,
                            "evidence_id": page["id"],
                            "status": "context_budget",
                        }
                    )
                    continue
                events.append(
                    {
                        "file": file,
                        "evidence_id": page["id"],
                        "status": "supplied",
                        "origin": origin,
                    }
                )
            if not offered:
                supplied = any(
                    p["kind"] == "code" and p["reference"].get("file") == file
                    for p in context["evidence"]
                )
                events.append(
                    {
                        "file": file,
                        "status": "already_supplied" if supplied else "no_source_pages",
                    }
                )
        except (ExecutionCancelled, AuditCancelled):
            raise
        except (OSError, UnicodeError) as exc:
            events.append(
                {"file": file, "status": "unavailable", "reason": str(exc)[:300]}
            )
        except AuditError as exc:
            if exc.code in {"identity_error", "integrity_error"}:
                raise
            events.append(
                {"file": file, "status": "unavailable", "reason": str(exc)[:300]}
            )
    context = refresh_citation_contract(refresh_control_context(service, context))
    return (_pack(context, maximum), events)


def next_feedback(service, batch_id, result, base, remaining, *, _kernel, context=None):
    current = service.repository.get(service.execution_id).result
    policy = current.get("review_feedback_policy", {})
    if not policy.get("enabled") or remaining < 1:
        return None
    if hashlib.sha256(policy["prompt"].encode()).hexdigest() != policy["prompt_hash"]:
        raise AuditError("补证提示冻结身份不一致", code="integrity_error")
    if policy["version"] == "2":
        from semflow_research.discovery.review_navigation_feedback import (
            next_navigation,
        )

        return next_navigation(
            service, batch_id, result, base, context or base, remaining, policy
        )
    attempted = {
        i
        for r in current.get("review_feedback_attempts", [])
        for i in r["candidate_ids"]
    }
    targets = {r["candidate_id"] for r in base["targets"]}
    for assessment in result.get("assessments", []):
        if (
            assessment["assessment"] != "insufficient"
            or assessment["candidate_id"] in attempted
            or assessment["candidate_id"] not in targets
        ):
            continue
        identifier = _begin_attempt(service, batch_id, assessment, remaining)
        files = missing_source_paths(assessment)
        if not files:
            update_attempt(service, identifier, status="no_local_source_target")
            continue
        if (
            snapshot_digest(service.evidence.root)
            != service.evidence.source_context.snapshot_hash
        ):
            raise AuditError("补证前源码快照发生变化", code="integrity_error")
        context = _target_context(base, assessment, batch_id, policy)
        try:
            context, events = _supply_pages(
                service, context, files, policy, _kernel=_kernel
            )
        except (ExecutionCancelled, AuditCancelled):
            raise
        except AuditError as exc:
            if exc.code in {"identity_error", "integrity_error"}:
                raise
            update_attempt(
                service, identifier, status="incomplete", code=exc.code, reason=str(exc)
            )
            continue
        update_attempt(service, identifier, status="prepared", source_events=events)
        if not any(e["status"] in {"supplied", "already_supplied"} for e in events):
            update_attempt(service, identifier, status="no_source_progress")
            continue
        return (context, identifier)
    return None
