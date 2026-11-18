"""Use the existing content store and checked review report as evidence memory."""

from hashlib import sha256

from semflow_contracts.common import canonical_bytes
from semflow_contracts.review_memory import (
    ReviewCachedSource,
    ReviewCacheReceipt,
    ReviewMemoryIdentity,
)

from semflow_research.public.runs import specification


def identity(spec, seed):
    subject = {
        "candidate": seed.candidate.model_dump(mode="json"),
        "security_property": seed.security_property,
        "readable_paths": spec.inputs.policy.scope_paths,
        "call_context": "exact_frozen_candidate_only",
    }
    analysis = {
        "implementation": spec.implementation.model_dump(mode="json"),
        "prompts": [(p.role, p.version, p.sha256) for p in spec.prompts],
        "model": spec.model.model_dump(mode="json") if spec.model else None,
    }
    return ReviewMemoryIdentity(
        snapshot_id=spec.source.snapshot_id,
        source_digest=spec.source.tree_sha256,
        subject_digest=sha256(canonical_bytes(subject)).hexdigest(),
        analysis_digest=sha256(canonical_bytes(analysis)).hexdigest(),
    )


def restore(context, service, seed):
    old = specification(seed.previous_execution_id, root=context.root)
    prior_key, current_key = identity(old, seed), identity(context.spec, seed)
    enabled = context.spec.inputs.policy.version != "1-no-cache"
    causes = [
        key
        for key in (
            "snapshot_id",
            "source_digest",
            "subject_digest",
            "analysis_digest",
            "validation_version",
        )
        if getattr(prior_key, key) != getattr(current_key, key)
    ]
    if not enabled:
        causes.append("cache_disabled")
    if seed.attempt is None:
        causes.append("legacy_fact_record_unavailable")

    # bundle_io already verified the imported ranges against the same frozen
    # snapshot. Source reuse remains safe across analyzer changes, facts do not.
    pages, source_receipts = [], []
    for evidence in seed.code_evidence:
        loc = evidence.location
        service.evidence.allowed(loc.path)
        view = {
            "file": loc.path,
            "start_line": loc.start_line,
            "end_line": loc.end_line,
        }
        if enabled:
            page = service.evidence.record(
                "code", context.artifacts.read(evidence.content).decode("utf-8"), view
            )
        else:
            page = service.evidence.read(**view)
        pages.append(page)
        source_receipts.append(
            ReviewCachedSource(
                previous_evidence_id=evidence.evidence_id,
                evidence_id=page["id"],
                location=loc,
                content_digest=page["digest"],
                disposition="reused" if enabled else "reread",
            )
        )
    mapping = {
        item.previous_evidence_id: str(item.evidence_id) for item in source_receipts
    }
    valid = [
        fact
        for fact in (seed.attempt.premises if seed.attempt else ())
        if fact.verification == "source_grounded"
    ]
    facts = [
        {
            "role": fact.role,
            "prior_status": fact.status,
            "explanation": fact.explanation,
            "policy_basis": fact.policy_basis,
            "quote": fact.quote,
            "evidence_ids": [mapping[ref.entity_id] for ref in fact.evidence_refs],
            "validation": "source_grounded",
        }
        for fact in valid
        if not causes and all(ref.entity_id in mapping for ref in fact.evidence_refs)
    ]
    if not causes and len(facts) < len(valid):
        causes.append("fact_source_not_reusable")
    receipt = ReviewCacheReceipt(
        mode="reuse" if enabled else "reread",
        previous=prior_key,
        current=current_key,
        source=tuple(source_receipts),
        source_hits=len(pages) if enabled else 0,
        source_misses=0 if enabled else len(pages),
        fact_hits=len(facts),
        fact_misses=len(valid) - len(facts),
        invalidation_reasons=tuple(causes),
    )
    return pages, facts, receipt
