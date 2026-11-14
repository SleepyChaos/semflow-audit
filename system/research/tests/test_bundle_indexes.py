"""Subset and producer capabilities must survive nested scientific collections."""

from uuid import uuid4

import pytest
from semflow_contracts.bundles import CandidateBundle, EvidenceBundle
from semflow_contracts.common import BundleRef, EntityRef
from semflow_contracts.discovery import CandidateRecord
from semflow_contracts.errors import ResearchError
from semflow_research.public.runtime import prepare
from semflow_research.runtime.bundle_io import import_targets
from semflow_research.runtime.bundle_reader import resolve_bundle
from semflow_research.runtime.discovery_merge import index
from semflow_research.runtime.discovery_outputs import commit_bundle
from semflow_research.state.models import Candidate


def inputs(case, settings):
    context = prepare(case.spec, root=case.ledger.root, settings=settings)
    evidence = context.source.read("app.py", 1, 1)
    evidence_ref = commit_bundle(
        context,
        EvidenceBundle(
            execution_id=case.execution_id,
            snapshot_id=case.snapshot.snapshot_id,
            records=(evidence,),
        ),
        "evidence_bundle",
    )
    rows = tuple(
        CandidateRecord(
            candidate_id=uuid4(),
            execution_id=case.execution_id,
            origin="scout",
            title="Input hypothesis",
            description="The source sends an input value into eval",
            weakness="CWE-95",
            primary_location=evidence.location,
            identity_key="input-" + str(ordinal),
            novelty="unknown",
            evidence_refs=(
                EntityRef(
                    execution_id=case.execution_id,
                    entity_id=evidence.evidence_id,
                    bundle=evidence_ref,
                ),
            ),
        )
        for ordinal in range(2)
    )
    ref = commit_bundle(
        context,
        CandidateBundle(
            execution_id=case.execution_id,
            snapshot_id=case.snapshot.snapshot_id,
            records=rows,
        ),
        "candidate_bundle",
    )
    return context, rows, ref, evidence_ref


def test_nested_index_keeps_selected_ids_and_rejects_overlapping_members(
    research_case, settings
):
    context, rows, ref, _ = inputs(research_case, settings)
    selected = BundleRef(artifact=ref, entity_ids=(rows[0].candidate_id,))
    outer = index(context, "candidate", (index(context, "candidate", (selected,)),))
    _, loaded = resolve_bundle(context, outer, CandidateBundle)
    assert (
        loaded.records == (rows[0],) and loaded.membership[rows[0].candidate_id] == ref
    )
    with pytest.raises(ResearchError, match="missing entity"):
        resolve_bundle(
            context,
            outer.model_copy(update={"entity_ids": (rows[1].candidate_id,)}),
            CandidateBundle,
        )
    duplicate = index(context, "candidate", (selected, BundleRef(artifact=ref)))
    with pytest.raises(ResearchError, match="overlapping"):
        resolve_bundle(context, duplicate, CandidateBundle)
    wrong = index(context, "evidence", ())
    with pytest.raises(ResearchError, match="artifact kind"):
        resolve_bundle(context, wrong, CandidateBundle)
    mislabeled = BundleRef(
        artifact=wrong.artifact.model_copy(update={"kind": "candidate_bundle"})
    )
    with pytest.raises(ResearchError, match="entity type"):
        resolve_bundle(context, mislabeled, CandidateBundle)


def test_bundle_import_cannot_enumerate_other_records_of_same_producer(
    research_case, settings
):
    from dataclasses import replace

    from semflow_research.runtime.artifacts import LocalArtifacts
    from semflow_research.runtime.evidence import SnapshotReader
    from semflow_research.state.records import RecordStore

    context, rows, ref, evidence_ref = inputs(research_case, settings)
    # Unselected mutable producer state exists alongside the frozen public inputs.
    hidden = Candidate(
        snapshot_id=research_case.snapshot.snapshot_id,
        execution_id=research_case.execution_id,
        origin="ai",
        title="Unrelated private record",
        description="Never selected as an input",
    )
    context.records.save(hidden)
    consumer = uuid4()
    artifacts = LocalArtifacts(
        context.artifacts.root,
        consumer,
        upstream=(ref, evidence_ref, research_case.snapshot.manifest),
    )
    received = replace(
        context,
        execution_id=consumer,
        artifacts=artifacts,
        source=SnapshotReader(
            context.source_root, research_case.snapshot, consumer, artifacts
        ),
        records=RecordStore(context.records.path, consumer, read_upstream=False),
    )
    received, selected = import_targets(
        received,
        BundleRef(artifact=ref, entity_ids=(rows[0].candidate_id,)),
        BundleRef(artifact=evidence_ref),
    )
    assert [row.candidate_id for row in selected] == [rows[0].candidate_id]
    assert {row.id for row in received.records.list(Candidate)} == {
        rows[0].candidate_id
    }
    assert received.records.get(Candidate, hidden.id) is None
    from semflow_research.adapters.artifacts import ArtifactStore
    from semflow_research.domain.errors import AuditError

    with pytest.raises(AuditError, match="冻结产物引用"):
        ArtifactStore(_kernel=received).directory(research_case.execution_id)
