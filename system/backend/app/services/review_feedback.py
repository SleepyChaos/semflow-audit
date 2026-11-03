"""Durable, candidate-specific supplementation inside the original batch allowance."""

import hashlib
from copy import deepcopy
from itertools import islice
from pathlib import Path

from app.adapters.context_packing import context_size, fit_navigation
from app.adapters.review_evidence import missing_source_paths, source_pages
from app.adapters.snapshot import snapshot_digest
from app.domain.audit import AuditCancelled, AuditError
from app.persistence.stage_repository import StageCancelled
from app.services.context_materials import digest, save_json
from app.services.discovery_context import (
    refresh_citation_contract,
    refresh_control_context,
)
from app.services.read_tools import window_observations


def initialize_feedback(service):
    current = service.repository.get(service.stage_id).result
    if "review_feedback_policy" in current:
        return
    prompt = (
        Path(__file__).resolve().parents[1] / "prompts/review-feedback.v1.txt"
    ).read_text()
    # A prepared historical run retains its original semantics on resume.
    policy = {
        "version": "1",
        "enabled": not current.get("pool")
        and service.stage.prompt_version in {"8", "9", "10", "11", "12"}
        and service.inputs.supplement_insufficient,
        "max_rounds_per_candidate": 1,
        "max_source_pages": 3,
        "model_allowance": "remaining_original_batch_steps_and_shared_provider_budget",
        "prompt": prompt,
        "prompt_hash": hashlib.sha256(prompt.encode()).hexdigest(),
    }
    service.repository.update(
        service.stage_id, result={**current, "review_feedback_policy": policy}
    )


def update_attempt(service, identifier, **values):
    current = service.repository.get(service.stage_id).result
    attempts = [
        ({**r, **values} if r["id"] == identifier else r)
        for r in current.get("review_feedback_attempts", [])
    ]
    service.repository.update(
        service.stage_id, result={**current, "review_feedback_attempts": attempts}
    )
    row = next(r for r in attempts if r["id"] == identifier)
    save_json(service.directory / "feedback" / identifier / "attempt.json", row)


def _begin_attempt(service, batch_id, assessment, remaining):
    current = service.repository.get(service.stage_id).result
    identifier = digest([batch_id, assessment["candidate_id"], "feedback-v1"])[:24]
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
    # Reserve durably before file/DB retrieval or model execution; resume cannot renew it.
    service.repository.update(
        service.stage_id,
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


def _supply_pages(service, context, files, policy):
    maximum = service.inputs.max_context_chars
    context = _pack(context, maximum)
    events, consumed = [], 0
    for file in files:
        if consumed >= policy["max_source_pages"]:
            events.append({"file": file, "status": "page_budget"})
            continue
        try:
            service.evidence.allowed(file)
            offered = False
            for page, origin in islice(
                source_pages(service.evidence, file, context["evidence"]),
                policy["max_source_pages"] - consumed,
            ):
                service.repository.active(service.stage_id)
                offered, consumed = True, consumed + 1
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
        except StageCancelled, AuditCancelled:
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
    return _pack(context, maximum), events


def next_feedback(service, batch_id, result, base, remaining):
    current = service.repository.get(service.stage_id).result
    policy = current.get("review_feedback_policy", {})
    if not policy.get("enabled") or remaining < 1:
        return None
    if hashlib.sha256(policy["prompt"].encode()).hexdigest() != policy["prompt_hash"]:
        raise AuditError("补证提示冻结身份不一致", code="integrity_error")
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
            != service.evidence.audit.snapshot_hash
        ):
            raise AuditError("补证前源码快照发生变化", code="integrity_error")
        context = _target_context(base, assessment, batch_id, policy)
        try:
            context, events = _supply_pages(service, context, files, policy)
        except StageCancelled, AuditCancelled:
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
        return context, identifier
    return None
