"""Read a published discovery result through typed, verified public codecs."""

from dataclasses import dataclass

from semflow_contracts.bundles import (
    AssessmentBundle,
    CandidateBundle,
    EvidenceBundle,
    StaticFindingBundle,
)
from semflow_contracts.common import BundleRef
from semflow_contracts.discovery_trace import DiscoveryTrace
from semflow_contracts.errors import ResearchError

from semflow_research.runtime.bundle_reader import read_bundle
from semflow_research.runtime.ledger import LocalLedger


@dataclass(frozen=True)
class DiscoveryView:
    candidates: tuple
    evidence: tuple
    assessments: tuple
    findings: tuple
    trace: DiscoveryTrace | None
    content: dict
    project_map: dict | None


def read_result(execution_id, *, root):
    ledger = LocalLedger(root)
    result = ledger.inspect(execution_id)
    if result is None or result.module != "discovery" or result.result is None:
        raise ResearchError("invalid_contract", "No published discovery payload")
    with ledger._connect() as db:
        row = ledger._row(db, execution_id)
        store = ledger._store(row)
        import json

        from semflow_contracts.runs import validate_spec

        spec = validate_spec(json.loads(row["spec"]))
    payload = result.result
    values = {}
    for name, reference, schema in (
        ("candidates", payload.candidates, CandidateBundle),
        ("evidence", payload.evidence, EvidenceBundle),
        ("assessments", payload.assessments, AssessmentBundle),
        ("findings", payload.static_findings, StaticFindingBundle),
    ):
        if reference is not None:
            store, loaded = read_bundle(
                store, spec.source.snapshot_id, reference, schema
            )
            values[name] = loaded.records
        else:
            values[name] = ()
    trace = None
    for candidate in values["candidates"]:
        if candidate.static_finding_ref is not None:
            static = candidate.static_finding_ref
            store, loaded = read_bundle(
                store,
                spec.source.snapshot_id,
                BundleRef(artifact=static.bundle, entity_ids=(static.entity_id,)),
                StaticFindingBundle,
            )
            values["findings"] = tuple(
                {
                    row.finding_id: row
                    for row in (*values["findings"], *loaded.records)
                }.values()
            )
    if payload.analysis_trace is not None:
        # WIRE-RECV:research.result — peer: runtime.discovery_outputs.export.
        # AGENT: trace is diagnostics only. Projection uses typed entities for
        # conclusions and must explicitly map identities, source digests and status.
        trace = DiscoveryTrace.model_validate_json(store.read(payload.analysis_trace))
        if (
            trace.execution_id,
            trace.snapshot_id,
            trace.source_digest,
            trace.method_version,
        ) != (
            execution_id,
            spec.source.snapshot_id,
            spec.source.tree_sha256,
            spec.implementation.method_version,
        ):
            raise ResearchError(
                "identity_mismatch",
                "Discovery trace belongs to another method or source",
            )
    return DiscoveryView(
        **values,
        trace=trace,
        project_map=json.loads(store.read(payload.project_map))
        if payload.project_map
        else None,
        content={
            row.evidence_id: store.read(row.content).decode("utf-8")
            for row in values["evidence"]
        },
    )
