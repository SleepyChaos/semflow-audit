"""Publish scientific discovery records as typed, independently verifiable JSON."""

import json
from uuid import UUID, uuid5

from semflow_contracts.bundles import (
    AssessmentBundle,
    CandidateBundle,
    EvidenceBundle,
    StaticFindingBundle,
    StaticFindingRecord,
)
from semflow_contracts.common import (
    BundleRef,
    EntityRef,
    SourceLocation,
    canonical_bytes,
)
from semflow_contracts.discovery import (
    AssessmentRecord,
    CandidateRecord,
    CoverageReport,
)
from semflow_contracts.discovery_trace import DiscoveryTrace
from semflow_contracts.evidence import EvidenceProvenance, EvidenceRecord
from semflow_contracts.results import DiscoveryResult

from semflow_research.state.models import Candidate, Evidence


def commit_bundle(context, bundle, kind):
    # WIRE-SEND:research.bundle — peer: runtime.bundle_io.load_bundle.
    # AGENT: keep producer/snapshot scope, subset membership and nested-reference
    # verification aligned with the receiver; never promote a model verdict here.
    return context.artifacts.commit(
        canonical_bytes(bundle), kind=kind, schema_version=bundle.schema_version
    )


def commit_json(
    context, data, kind="materials", version="semflow.scientific-materials/1"
):
    return context.artifacts.commit(
        canonical_bytes(data), kind=kind, schema_version=version
    )


def location(context, value):
    name = value["file"]
    entry = context.source.files[name]
    start = value.get("start_line", value.get("line", 1))
    end = value.get("end_line", start)
    # Reading verifies actual line bounds as well as bytes, without inventing a
    # replacement location when an external tool emits an invalid source range.
    context.source._slice(name, start, end)
    return SourceLocation(
        snapshot_id=context.spec.source.snapshot_id,
        path=name,
        start_line=start,
        end_line=end,
        file_sha256=entry.sha256,
        start_column=value.get("column") or None,
        end_column=value.get("end_column") or None,
    )


def export_evidence(context):
    records = context.records.list(Evidence, execution_id=context.execution_id)
    exported = []
    for row in records:
        content = context.artifacts.commit(
            row.content.encode(),
            kind="source_slice" if row.kind == "code" else "materials",
            schema_version="semflow.source-slice/1"
            if row.kind == "code"
            else "semflow.tool-observation/1",
            media_type="text/plain",
        )
        kind = row.kind if row.kind in {"code", "query", "knowledge"} else "tool"
        exported.append(
            EvidenceRecord(
                evidence_id=row.id,
                execution_id=row.execution_id,
                snapshot_id=row.snapshot_id,
                kind=kind,
                content=content,
                digest=row.digest,
                location=location(context, row.reference) if kind == "code" else None,
                provenance=EvidenceProvenance(
                    producer="semflow_research." + row.kind,
                    call_id=UUID(row.provenance["call_id"])
                    if row.provenance.get("call_id")
                    else None,
                    input_refs=(context.spec.source.manifest,),
                ),
            )
        )
    bundle = EvidenceBundle(
        execution_id=context.execution_id,
        snapshot_id=context.spec.source.snapshot_id,
        records=tuple(exported),
    )
    return commit_bundle(context, bundle, "evidence_bundle"), {
        row.evidence_id for row in exported
    }


def export(context, *, static_ref=None):
    execution = context.execution_records.get(context.execution_id)
    raw = execution.result
    evidence_ref, evidence_ids = export_evidence(context)
    evidence = lambda identifier: EntityRef(
        execution_id=context.execution_id,
        entity_id=UUID(str(identifier)),
        bundle=evidence_ref,
    )
    rows = context.records.list(Candidate, execution_id=context.execution_id)
    hypotheses = {
        item["candidate_id"]: item
        for unit in raw.get("units", [])
        for item in unit.get("hypotheses", [])
    }
    hypotheses.update(
        {
            row["candidate_id"]: row["hypothesis"]
            for row in raw.get("pool", {}).get("entries", [])
        }
    )
    candidates = []
    for row in rows:
        if not {UUID(value) for value in row.evidence_ids}.issubset(evidence_ids):
            raise ValueError(
                "Candidate references evidence outside its producing execution"
            )
        original_static_ref = static_ref or context.source_records.get(
            context.spec.source.snapshot_id
        ).finding_refs.get(row.static_finding_id)
        static = (
            EntityRef(
                execution_id=original_static_ref.owner_execution_id,
                entity_id=uuid5(context.spec.source.snapshot_id, row.static_finding_id),
                bundle=original_static_ref,
            )
            if row.static_finding_id and original_static_ref
            else None
        )
        candidates.append(
            CandidateRecord(
                candidate_id=row.id,
                execution_id=row.execution_id,
                origin="codeql"
                if row.origin == "static"
                else "scout"
                if execution.kind == "scout"
                else "review",
                title=row.title,
                description=row.description,
                weakness=row.weakness,
                primary_location=location(context, row.location),
                identity_key=row.identity_key,
                static_finding_ref=static,
                derived_from=row.source_ref,
                novelty="known_location"
                if row.novelty in {"baseline", "overlaps_static"}
                else "new_location"
                if row.novelty == "new_location"
                else "unknown",
                evidence_refs=tuple(evidence(value) for value in row.evidence_ids),
                context=commit_json(
                    context, hypotheses[str(row.id)], version="semflow.hypothesis/1"
                )
                if str(row.id) in hypotheses
                else None,
            )
        )
    candidate_ref = commit_bundle(
        context,
        CandidateBundle(
            execution_id=context.execution_id,
            snapshot_id=context.spec.source.snapshot_id,
            records=tuple(candidates),
        ),
        "candidate_bundle",
    )
    entity = lambda identifier: EntityRef(
        execution_id=context.execution_id,
        entity_id=UUID(str(identifier)),
        bundle=candidate_ref,
    )
    assessments = []
    for batch in raw.get("batches", []):
        for row in batch.get("assessments", []):
            assessments.append(
                AssessmentRecord(
                    assessment_id=uuid5(context.execution_id, str(row["candidate_id"])),
                    candidate_ref=entity(row["candidate_id"]),
                    conclusion=row["assessment"],
                    checked_premises=tuple(row.get("checked_premises", [])),
                    unknown_premises=tuple(row.get("missing_premises", [])),
                    evidence_refs=tuple(
                        evidence(value) for value in row["evidence_ids"]
                    ),
                    counter_evidence_refs=tuple(
                        evidence(value) for value in row.get("counterevidence_ids", [])
                    ),
                    reason=row["reason"],
                )
            )
    assessment_ref = (
        commit_bundle(
            context,
            AssessmentBundle(
                execution_id=context.execution_id,
                snapshot_id=context.spec.source.snapshot_id,
                records=tuple(assessments),
            ),
            "materials",
        )
        if assessments
        else None
    )
    candidate_reviews = None
    if execution.kind == "review" and "candidate_handoffs" in raw:
        from semflow_research.runtime.review_report import build_report

        candidate_reviews = commit_bundle(
            context,
            build_report(context, raw, candidates, assessments, entity, evidence),
            "materials",
        )
    coverage = raw.get("coverage", {})
    unknown = set(raw.get("unreviewed_candidate_ids", []))
    inspected = [row for row in raw.get("units", []) if row["status"] == "inspected"]
    partial = (
        coverage.get("status") == "partial" or raw.get("coverage_status") == "partial"
    )
    report = CoverageReport(
        status="partial" if partial else "full",
        scope_manifest=commit_json(
            context,
            coverage or {"candidate_ids": [str(row.id) for row in rows]},
            "coverage",
        ),
        inspected_units=commit_json(
            context,
            inspected if execution.kind == "scout" else raw.get("batches", []),
            "coverage",
        ),
        missing_units=commit_json(
            context,
            [row for row in raw.get("units", []) if row["status"] != "inspected"]
            if execution.kind == "scout"
            else sorted(unknown),
            "coverage",
        ),
        reasons=(
            str(
                raw.get("stop_reason")
                or coverage.get("stop_reason")
                or "Uninspected source or candidate scopes remain"
            ),
        )
        if partial
        else (),
        reviewed_candidate_refs=tuple(
            entity(row.id)
            for row in rows
            if execution.kind == "review" and str(row.id) not in unknown
        ),
        unreviewed_candidate_refs=tuple(entity(value) for value in sorted(unknown)),
    )
    return DiscoveryResult(
        project_map=commit_json(
            context,
            json.loads((context.workspace / "scout-map.json").read_bytes()),
            version="semflow.scout-map/1",
        )
        if execution.kind == "scout"
        and (context.workspace / "scout-map.json").is_file()
        else None,
        candidate_reviews=candidate_reviews,
        analysis_trace=commit_json(
            context,
            DiscoveryTrace(
                execution_id=context.execution_id,
                snapshot_id=context.spec.source.snapshot_id,
                source_digest=context.spec.source.tree_sha256,
                method_version=context.spec.implementation.method_version,
                state=raw,
                usage=execution.usage,
                model_calls=tuple(execution.model_calls),
            ),
            version="semflow.discovery-trace/1",
        ),
        static_findings=BundleRef(artifact=static_ref) if static_ref else None,
        candidates=BundleRef(artifact=candidate_ref),
        evidence=BundleRef(artifact=evidence_ref),
        assessments=BundleRef(artifact=assessment_ref) if assessment_ref else None,
        coverage=report,
        root_relations=commit_json(context, raw["root_relations"])
        if "root_relations" in raw
        else None,
    )


def export_static(context, findings, sarif_ref):
    records = tuple(
        StaticFindingRecord(
            finding_id=uuid5(context.spec.source.snapshot_id, row["id"]),
            execution_id=context.execution_id,
            raw_id=row["id"],
            rule_version=row.get("rule_version"),
            origin=row.get("origin", "baseline"),
            rule=row["rule"],
            message=row["message"],
            locations=tuple(location(context, point) for point in row["locations"]),
            code_flows=tuple(
                tuple(location(context, point) for point in flow)
                for flow in row["code_flows"]
            ),
            tags=tuple(row["tags"]),
            level=row["level"],
            security_severity=str(row["security_severity"])
            if row["security_severity"] is not None
            else None,
            sarif=sarif_ref,
        )
        for row in findings
    )
    return commit_bundle(
        context,
        StaticFindingBundle(
            execution_id=context.execution_id,
            snapshot_id=context.spec.source.snapshot_id,
            records=records,
        ),
        "materials",
    )
