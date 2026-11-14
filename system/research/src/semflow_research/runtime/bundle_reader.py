"""Verify leaf bundles and coordinator indexes without changing record identity."""

from dataclasses import dataclass, replace
from uuid import UUID

from semflow_contracts.bundles import (
    AssessmentBundle,
    BundleIndex,
    CandidateBundle,
    DecisionBundle,
    EvidenceBundle,
    StaticFindingBundle,
)
from semflow_contracts.common import ArtifactRef, BundleRef
from semflow_contracts.errors import ResearchError

from semflow_research.runtime.artifacts import LocalArtifacts
from semflow_research.runtime.evidence import SnapshotReader
from semflow_research.runtime.ledger import input_artifacts
from semflow_research.state.records import RecordStore

SCHEMAS = {
    CandidateBundle: ("candidate_id", "candidate", "candidate_bundle"),
    EvidenceBundle: ("evidence_id", "evidence", "evidence_bundle"),
    DecisionBundle: ("decision_id", "decision", "decision_bundle"),
    AssessmentBundle: ("assessment_id", "assessment", "materials"),
    StaticFindingBundle: ("finding_id", "static_finding", "materials"),
}


@dataclass(frozen=True)
class BundleRead:
    records: tuple
    membership: dict[UUID, ArtifactRef]
    producers: frozenset[UUID]


def extend_store(artifacts, refs):
    """Grant only byte references present in a verified typed payload."""
    refs = tuple(refs)
    current = tuple(
        ArtifactRef.model_validate_json(value) for value in artifacts.upstream
    )
    result = LocalArtifacts(
        artifacts.root, artifacts.execution_id, upstream=current + refs
    )
    for ref in refs:
        result.read(ref)
    return result


def authorize_artifacts(context, refs):
    artifacts = extend_store(context.artifacts, refs)
    return replace(
        context,
        artifacts=artifacts,
        source=SnapshotReader(
            context.source_root, context.spec.source, context.execution_id, artifacts
        ),
    )


def resolve_bundle(context, reference, schema):
    artifacts, loaded = read_bundle(
        context.artifacts, context.spec.source.snapshot_id, reference, schema
    )
    return replace(
        context,
        artifacts=artifacts,
        source=SnapshotReader(
            context.source_root, context.spec.source, context.execution_id, artifacts
        ),
    ), loaded


def read_bundle(artifacts, snapshot_id, reference: BundleRef, schema, *, _ancestors=()):
    reference = BundleRef.model_validate_json(reference.model_dump_json())
    key, entity_type, kind = SCHEMAS[schema]
    ref = reference.artifact
    identity = (ref.owner_execution_id, ref.sha256)
    if len(_ancestors) >= 8 or identity in _ancestors:
        raise ResearchError(
            "invalid_contract", "Bundle index chain is cyclic or too deep"
        )
    if ref.kind != kind:
        raise ResearchError(
            "invalid_contract",
            "Input artifact kind does not match the requested records",
        )
    raw = artifacts.read(ref)
    if ref.schema_version == "semflow.research.bundle-index/1":
        # WIRE-RECV:research.bundle_index — peer: discovery_merge.index.
        # AGENT: preserve leaf owners and exact membership across both ends;
        # index traversal must never grant access to other records of an owner.
        index = BundleIndex.model_validate_json(raw)
        if (
            index.execution_id != ref.owner_execution_id
            or index.snapshot_id != snapshot_id
            or index.entity_type != entity_type
        ):
            raise ResearchError(
                "identity_mismatch",
                "Bundle index owner, snapshot or entity type changed",
            )
        artifacts = extend_store(
            artifacts, tuple(member.artifact for member in index.members)
        )
        records, membership, producers = [], {}, set()
        for member in index.members:
            artifacts, nested = read_bundle(
                artifacts,
                snapshot_id,
                member,
                schema,
                _ancestors=(*_ancestors, identity),
            )
            if set(membership) & nested.membership.keys():
                raise ResearchError(
                    "identity_mismatch",
                    "Bundle index contains overlapping entity identities",
                )
            records.extend(nested.records)
            membership.update(nested.membership)
            producers.update(nested.producers)
    elif ref.schema_version == "semflow.research.bundle/1":
        # WIRE-RECV:research.bundle — peer: discovery_outputs.commit_bundle.
        # AGENT: verify producer, real bytes, selected IDs and nested capabilities;
        # a type-correct JSON body alone cannot establish evidence or ownership.
        bundle = schema.model_validate_json(raw)
        if (
            bundle.execution_id != ref.owner_execution_id
            or bundle.snapshot_id != snapshot_id
        ):
            raise ResearchError(
                "identity_mismatch",
                "Input bundle producer or snapshot does not match its reference",
            )
        available = {getattr(record, key): record for record in bundle.records}
        selected = (
            set(reference.entity_ids)
            if reference.entity_ids is not None
            else set(available)
        )
        if not selected.issubset(available):
            raise ResearchError(
                "identity_mismatch", "Bundle selection contains missing entity IDs"
            )
        records = [
            record for record in bundle.records if getattr(record, key) in selected
        ]
        artifacts = extend_store(artifacts, input_artifacts(records))
        membership = {getattr(record, key): ref for record in records}
        producers = {bundle.execution_id}
    else:
        raise ResearchError("unsupported_version", "Unknown scientific bundle format")
    selected = (
        set(reference.entity_ids)
        if reference.entity_ids is not None
        else set(membership)
    )
    if not selected.issubset(membership):
        raise ResearchError(
            "identity_mismatch", "Bundle selection contains missing entity IDs"
        )
    records = tuple(record for record in records if getattr(record, key) in selected)
    return artifacts, BundleRead(
        records=records,
        membership={
            identifier: ref
            for identifier, ref in membership.items()
            if identifier in selected
        },
        producers=frozenset(producers),
    )


def load_bundle(context, reference, schema):
    context, loaded = resolve_bundle(context, reference, schema)
    return context, loaded.records


def authorize_records(context, producers):
    """Explicit input import scope, separate from artifact read capabilities."""
    return replace(
        context,
        records=RecordStore(
            context.records.path,
            context.execution_id,
            tuple(
                dict.fromkeys((*context.records.scope[1:], *sorted(producers, key=str)))
            ),
            read_upstream=context.records.read_upstream,
        ),
    )
