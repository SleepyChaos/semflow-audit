"""Algorithm extracted from app.services.unified_review_results.

Runtime dependencies are passed explicitly; no platform ORM or configuration.
Changes to JSON require checking the corresponding semflow_contracts/wire peer.
"""

"""Validate candidate verdicts independently, preserving all source hypotheses."""
from collections import Counter

from semflow_research.adapters.source_inventory import inspectable
from semflow_research.domain.errors import AuditError, ExecutionCancelled
from semflow_research.evidence.context_materials import digest
from semflow_research.evidence.read_tools import grounded
from semflow_research.state.models import Candidate, ExecutionRecord


def save_batch(service, batch_id, response, context, *, call_reference=None, _kernel):
    seen = {r["id"]: r for r in context["evidence"]}
    targets = {r["candidate_id"]: r for r in context["targets"]}

    def evidence(ids, location=None):
        if not set(map(str, ids)).issubset(seen):
            raise AuditError("复核引用了未取得的证据")
        rows = [seen[str(i)] for i in set(ids)]
        if location and (not grounded(rows, location)):
            raise AuditError("复核结论必须引用目标位置的实际源码")
        return rows

    checked, recommendations = (set(), [])
    accepted_assessments, rejected_assessments = ([], [])
    classifications = []
    with _kernel.records.transaction() as db:
        stage = db.one(ExecutionRecord, id=service.execution.id)
        if stage.status == "cancelled":
            raise ExecutionCancelled("复核已取消")
        counts = Counter(str(a.candidate_id) for a in response.candidate_assessments)
        for assessment in response.candidate_assessments:
            identifier = str(assessment.candidate_id)
            if (
                identifier not in targets
                or identifier in checked
                or (
                    stage.method_version in {"8", "9", "10", "11", "12"}
                    and counts[identifier] > 1
                )
            ):
                if stage.method_version not in {"8", "9", "10", "11", "12"}:
                    raise AuditError("复核候选无效或重复")
                rejected_assessments.append(
                    {
                        "candidate_id": identifier,
                        "reason": "Invalid or repeated candidate identity",
                    }
                )
                continue
            checked.add(identifier)
            from semflow_research.discovery.review_verdict_gate import (
                validate_assessment,
            )

            try:
                validate_assessment(service, assessment, context, targets, evidence)
            except AuditError as exc:
                if stage.method_version not in {"8", "9", "10", "11", "12"}:
                    raise
                rejected_assessments.append(
                    {
                        "candidate_id": identifier,
                        "reason": str(exc),
                        "code": exc.code,
                        "assessment": assessment.model_dump(mode="json"),
                    }
                )
                checked.discard(identifier)
                continue
            accepted_assessments.append(assessment)
            row = db.get(Candidate, assessment.candidate_id)
            if (
                row is None
                or row.execution_id != stage.id
                or row.snapshot_id != stage.snapshot_id
            ):
                raise AuditError("复核目标跨阶段", code="identity_error")
            row.model_assessment = assessment.assessment
            if stage.method_version == "12":
                from semflow_research.discovery.candidate_classification import (
                    apply_model_classification,
                )

                apply_model_classification(row, assessment.assessment, db)
                row.title = assessment.detail.title
                row.description = assessment.detail.description
            if stage.method_version in {"8", "9", "10", "11", "12"}:
                from semflow_research.discovery.review_classification import decision

                classification = decision(row.weakness, assessment.weakness)
                row.weakness = classification["effective_weakness"]
                classifications.append({"candidate_id": identifier, **classification})
            else:
                row.weakness = assessment.weakness
            row.evidence_ids = list(
                map(str, set(assessment.evidence_ids + assessment.counterevidence_ids))
            )
            db.save(row)
            recommendations.append(
                {"id": identifier, "recommendation": assessment.assessment}
            )
        accepted_relations, rejected_relations = ([], [])
        for relation in response.root_relations:
            try:
                identifiers = set(map(str, relation.candidate_ids))
                if len(identifiers) != len(
                    relation.candidate_ids
                ) or not identifiers.issubset(targets):
                    raise AuditError("根因关联目标无效")
                rows = evidence(relation.evidence_ids)
                if not all(grounded(rows, targets[i]["location"]) for i in identifiers):
                    raise AuditError("根因关联需要覆盖各目标的源码证据")
            except AuditError as exc:
                rejected_relations.append(
                    {"proposal": relation.model_dump(mode="json"), "reason": str(exc)}
                )
            else:
                accepted_relations.append(relation.model_dump(mode="json"))
        rejected_findings = []
        for finding in response.new_findings:
            try:
                if (
                    context.get("feedback_revision")
                    or not service.inputs.discover
                    or finding.related_target not in targets
                ):
                    raise AuditError("复核补充发现未授权或关联目标无效")
                location = finding.primary_location.model_dump()
                if not inspectable(
                    location["file"], service.evidence.source_context.language
                ):
                    raise AuditError("复核补充假设必须位于实际项目源码")
                service.evidence.allowed(location["file"])
                evidence(finding.evidence_ids, location)
            except AuditError as exc:
                if stage.method_version not in {"8", "9", "10", "11", "12"}:
                    raise
                rejected_findings.append(
                    {"finding": finding.model_dump(mode="json"), "reason": str(exc)}
                )
                continue
            identity = "review:" + digest(
                {
                    "snapshot": service.evidence.source_context.snapshot_hash,
                    "finding": finding.model_dump(mode="json"),
                }
            )
            row = db.first(Candidate, execution_id=stage.id, identity_key=identity)
            if row is None:
                row = Candidate(
                    snapshot_id=stage.snapshot_id,
                    execution_id=stage.id,
                    origin="ai",
                    title=finding.title,
                    description=finding.description,
                    weakness=finding.weakness,
                    location=location,
                    related_target=finding.related_target,
                    model_assessment="pending",
                    evidence_ids=list(map(str, finding.evidence_ids)),
                    identity_key=identity,
                    novelty="unverified",
                )
                db.save(row)
            recommendations.append({"id": str(row.id), "recommendation": "pending"})
        if response.anchor_assessments and stage.method_version not in {
            "8",
            "9",
            "10",
            "11",
            "12",
        }:
            raise AuditError("统一复核批次没有提供锚点评价目标")
        result = {
            "batch_id": batch_id,
            "status": "partial"
            if stage.method_version in {"8", "9", "10", "11", "12"}
            and set(targets) - checked
            else "completed",
            "summary": response.summary,
            "candidate_ids": list(targets),
            "assessments": [r.model_dump(mode="json") for r in accepted_assessments],
            "classifications": classifications,
            "rejected_assessments": rejected_assessments,
            "recommendations": recommendations,
            "unreviewed_candidate_ids": sorted(set(targets) - checked),
            "root_relations": accepted_relations,
            "rejected_root_relations": rejected_relations,
            "rejected_new_findings": rejected_findings,
            "rejected_anchor_assessments": [
                a.model_dump(mode="json") for a in response.anchor_assessments
            ],
            "trace": context["tool_trace"],
            "call_reference": call_reference,
        }
        previous = {r["batch_id"]: r for r in stage.result.get("batches", [])}
        from semflow_research.discovery.review_batch_history import merge_revision

        result = merge_revision(
            previous.get(batch_id, {}), result, context.get("feedback_revision")
        )
        previous[batch_id] = result
        stage.result = {**stage.result, "batches": list(previous.values())}
        db.save(stage)
        db.commit()
    return result
