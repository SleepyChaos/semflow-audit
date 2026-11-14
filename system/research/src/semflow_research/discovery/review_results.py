"""Algorithm extracted from app.services.review_results.

Runtime dependencies are passed explicitly; no platform ORM or configuration.
Changes to JSON require checking the corresponding semflow_contracts/wire peer.
"""

"""Atomic V2 result validation and storage; human decisions are independent."""
import hashlib
import json

from semflow_contracts.modelio.review import ReviewResponseV2

from semflow_research.domain.errors import AuditError, ExecutionCancelled
from semflow_research.evidence.evidence import valid_evidence
from semflow_research.state.models import Candidate, ExecutionRecord, get_datetime_utc


def save_v2(service, state: dict, *, _kernel) -> dict:
    response = ReviewResponseV2.model_validate(state["response"])
    context = state["context"]
    anchor_locations = {row["id"]: row for row in context["anchors"]}
    anchors = set(anchor_locations)
    targets = {row["candidate_id"] for row in context["targets"]}
    seen = {row["id"] for row in context["evidence"]}
    assessed_anchors, assessed_candidates = (set(), set())
    saved = []

    def evidence(ids, require=True):
        if not set(map(str, ids)).issubset(seen):
            raise AuditError("模型引用了未取到的证据")
        return valid_evidence(
            service.execution.snapshot_id, ids, require, _kernel=_kernel
        )

    def grounded(records, location):
        return any(
            row.kind == "code"
            and row.reference.get("file") == location["file"]
            and (
                row.reference["start_line"]
                <= location["line"]
                <= row.reference["end_line"]
            )
            for row in records
        )

    with _kernel.records.transaction() as session:
        stage = session.one(ExecutionRecord, id=service.execution.id)
        if stage.status == "cancelled":
            raise ExecutionCancelled("阶段已取消")
        for row in response.anchor_assessments:
            if row.anchor_id not in anchors or row.anchor_id in assessed_anchors:
                raise AuditError("锚点评价ID无效或重复")
            records = evidence(row.evidence_ids, row.assessment != "insufficient")
            if row.assessment != "insufficient" and (
                not grounded(records, anchor_locations[row.anchor_id])
            ):
                raise AuditError("锚点评价必须引用该锚点位置的源码证据")
            assessed_anchors.add(row.anchor_id)
        for row in response.candidate_assessments:
            identifier = str(row.candidate_id)
            if identifier not in targets or identifier in assessed_candidates:
                raise AuditError("候选评价ID无效或重复")
            records = evidence(
                row.evidence_ids, row.assessment in {"supported", "excluded"}
            )
            candidate = session.get(Candidate, row.candidate_id)
            if row.assessment in {"supported", "excluded"} and (
                not grounded(records, candidate.location)
            ):
                raise AuditError("候选评价必须引用该候选位置的源码证据")
            candidate.model_assessment = row.assessment
            candidate.weakness = row.weakness
            candidate.description = row.reason
            candidate.evidence_ids = list(map(str, row.evidence_ids))
            session.save(candidate)
            assessed_candidates.add(identifier)
            saved.append({"id": identifier, "recommendation": row.assessment})
        identities = set()
        for row in response.new_findings:
            if (
                not service.inputs.discover
                or row.related_target not in anchors | targets
            ):
                raise AuditError("补充发现未授权或关联目标无效")
            location = row.primary_location.model_dump()
            service.evidence.allowed(location["file"])
            records = evidence(row.evidence_ids)
            if not any(
                r.kind == "code"
                and r.reference.get("file") == location["file"]
                and (
                    r.reference["start_line"]
                    <= location["line"]
                    <= r.reference["end_line"]
                )
                for r in records
            ):
                raise AuditError("补充发现主位置必须落在已取得的源码证据内")
            identity = hashlib.sha256(
                json.dumps(
                    [
                        service.evidence.source_context.snapshot_hash,
                        location,
                        row.weakness,
                    ],
                    sort_keys=True,
                ).encode()
            ).hexdigest()
            if identity in identities:
                raise AuditError("重复补充发现")
            identities.add(identity)
            overlaps = any(
                loc["file"] == location["file"] and loc["line"] == location["line"]
                for finding in service.evidence.source_context.findings
                for loc in finding["locations"]
            )
            candidate = Candidate(
                snapshot_id=service.execution.snapshot_id,
                execution_id=service.execution.id,
                origin="ai",
                title=row.title,
                description=row.description,
                weakness=row.weakness,
                model_assessment="supported",
                related_target=row.related_target,
                identity_key="ai:" + identity,
                location=location,
                evidence_ids=list(map(str, row.evidence_ids)),
                novelty="overlaps_static" if overlaps else "new_location",
            )
            session.save(candidate)
            saved.append({"id": str(candidate.id), "recommendation": "supported"})
        reviewed = [
            row["static_alert"]["id"]
            for row in context["targets"]
            if row["candidate_id"] in assessed_candidates
        ]
        result = {
            "schema_version": "2",
            "summary": response.summary,
            "recommendations": saved,
            "candidate_ids": [row["id"] for row in saved],
            "anchor_assessments": [
                row.model_dump(mode="json") for row in response.anchor_assessments
            ],
            "unreviewed_anchor_ids": sorted(anchors - assessed_anchors),
            "unreviewed_candidate_ids": sorted(targets - assessed_candidates),
            "reviewed_static_finding_ids": reviewed,
            "unreviewed_static_finding_ids": [
                row["id"]
                for row in service.evidence.source_context.findings
                if row["id"] not in reviewed
            ],
            "anchors": context["anchors"],
            "trace": context["tool_trace"],
            "snapshot_hash": service.evidence.source_context.snapshot_hash,
        }
        stage.status = "completed"
        stage.phase = "awaiting_human_decisions"
        stage.result = result
        stage.updated_at = get_datetime_utc()
        session.save(stage)
        session.commit()
    return {"saved": True}
