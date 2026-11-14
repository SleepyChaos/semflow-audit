"""Local explicit human selection of immutable upstream discovery targets."""

from datetime import UTC, datetime
from uuid import uuid4

from semflow_contracts.bundles import CandidateBundle, DecisionBundle
from semflow_contracts.common import BundleRef, EntityRef, canonical_bytes
from semflow_contracts.errors import ResearchError
from semflow_contracts.evidence import ActorRef, DecisionRecord, TargetBundle

from semflow_research.public.runs import inspect, specification
from semflow_research.runtime.artifacts import LocalArtifacts
from semflow_research.runtime.bundle_reader import read_bundle
from semflow_research.runtime.ledger import input_artifacts


def select_targets(
    *,
    root,
    upstream_execution_id,
    execution_id,
    candidate_ids,
    actor,
    confirmation_reason,
):
    previous = inspect(upstream_execution_id, root=root)
    upstream = specification(upstream_execution_id, root=root)
    if previous is None or previous.module != "discovery" or previous.result is None:
        raise ResearchError(
            "invalid_contract", "Repair input requires a published discovery result"
        )
    if not candidate_ids or len(set(candidate_ids)) != len(candidate_ids):
        raise ResearchError(
            "invalid_contract", "Select distinct candidate identities explicitly"
        )
    artifacts = LocalArtifacts(
        root / "artifacts",
        execution_id,
        upstream=input_artifacts(previous) + input_artifacts(upstream),
    )
    candidates = BundleRef(
        artifact=previous.result.candidates.artifact, entity_ids=candidate_ids
    )
    artifacts, selected = read_bundle(
        artifacts, upstream.source.snapshot_id, candidates, CandidateBundle
    )
    decisions = []
    for row in selected.records:
        decisions.append(
            DecisionRecord(
                decision_id=uuid4(),
                target=EntityRef(
                    execution_id=row.execution_id,
                    entity_id=row.candidate_id,
                    bundle=selected.membership[row.candidate_id],
                ),
                snapshot_id=upstream.source.snapshot_id,
                status="confirmed",
                actor=ActorRef(kind="human", id=actor),
                reason=confirmation_reason,
                evidence_refs=row.evidence_refs,
                created_at=datetime.now(UTC),
            )
        )
    decision_ref = artifacts.commit(
        canonical_bytes(
            DecisionBundle(
                execution_id=execution_id,
                snapshot_id=upstream.source.snapshot_id,
                records=tuple(decisions),
            )
        ),
        kind="decision_bundle",
        schema_version="semflow.research.bundle/1",
    )
    return upstream.source, TargetBundle(
        snapshot_id=upstream.source.snapshot_id,
        candidates=candidates,
        evidence=previous.result.evidence,
        decisions=BundleRef(artifact=decision_ref),
    )
