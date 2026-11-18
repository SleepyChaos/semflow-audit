"""Bind a frozen, single-target review retry to verified source pages."""

from semflow_contracts.errors import ResearchError

from semflow_research.evidence.read_tools import grounded
from semflow_research.public.review_continuation import capture, require_continuable


def attach(context, service, previous, candidates):
    if len(candidates) != 1:
        raise ResearchError("invalid_contract", "Continuation requires one candidate")
    candidate = candidates[0]
    seed = capture(
        previous, candidate.candidate_id, source=context.spec.source, root=context.root
    )
    require_continuable(seed)
    if candidate != seed.candidate:
        raise ResearchError(
            "identity_mismatch", "Continuation changed original candidate"
        )
    selected = context.spec.inputs.evidence.entity_ids
    if selected is None or set(selected) != set(seed.evidence_ids):
        raise ResearchError(
            "identity_mismatch", "Continuation changed selected evidence"
        )
    pages, citations = [], []
    for evidence in seed.code_evidence:
        location = evidence.location
        service.evidence.allowed(location.path)
        page = service.evidence.record(
            "code",
            context.artifacts.read(evidence.content).decode("utf-8"),
            {
                "file": location.path,
                "start_line": location.start_line,
                "end_line": location.end_line,
            },
        )
        pages.append(page)
        citations.append(
            {
                "previous_evidence_id": str(evidence.evidence_id),
                "evidence_id": page["id"],
            }
        )
    point = {
        "file": candidate.primary_location.path,
        "line": candidate.primary_location.start_line,
    }
    anchor = next((page for page in pages if grounded([page], point)), None)
    if anchor is None:
        raise ResearchError(
            "evidence_invalid", "Prior evidence does not cover the target"
        )
    added = []
    if seed.next_action is not None:
        for window in seed.next_action.source_windows:
            page = service.evidence.read(**window.model_dump())
            if page["id"] not in {existing["id"] for existing in pages}:
                pages.append(page)
                added.append({"evidence_id": page["id"], **page["reference"]})
    if (
        seed.next_action is not None
        and seed.next_action.kind == "gather_source"
        and not added
    ):
        raise ResearchError(
            "evidence_invalid", "Planned continuation did not produce new evidence"
        )
    assessment = seed.assessment
    summary = {
        "previous_execution_id": str(previous),
        "previous_candidate_id": str(candidate.candidate_id),
        "security_property": seed.security_property,
        "previous_conclusion": assessment.conclusion if assessment else None,
        "purpose": seed.next_action.kind if seed.next_action else "legacy_continuation",
        "new_source_evidence": added,
        "checked_premises": list(assessment.checked_premises) if assessment else [],
        "missing_premises": list(assessment.unknown_premises) if assessment else [],
        "conclusion_contract": {
            "supported": "Verified evidence establishes the reported defect.",
            "excluded": "Verified counterevidence rules out the reported defect within scope.",
            "insufficient": "A premise necessary to decide the reported defect remains unresolved.",
        },
        "instruction": "Assess whether the reported defect exists, not whether the code satisfies the security property. Keep the same security property. Reuse supplied source pages and investigate only missing premises. Prior opinions are context, not proof. Preserve uncertainty when evidence is still missing.",
    }
    service.continuation = {"anchor": anchor, "pages": pages, "summary": summary}
    current = service.repository.get(service.execution_id).result
    service.repository.update(
        service.execution_id,
        result={
            **current,
            "review_continuation": {
                **summary,
                "reused_evidence": citations,
                "previous_source_windows": [
                    row.model_dump(mode="json") for row in seed.observed_windows
                ],
            },
        },
    )
