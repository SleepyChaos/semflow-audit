"""Expose only accepted assessments from the candidate's own immutable review stage."""


def candidate_review(candidate, stages, snapshot_hash):
    stage = stages.get(candidate.stage_id)
    if stage is None or stage.kind != "review" or stage.audit_id != candidate.audit_id:
        return None
    if (
        stage.result.get("snapshot_hash", stage.result.get("pool", {}).get("snapshot"))
        != snapshot_hash
    ):
        return None
    identifier = str(candidate.id)
    assessments = [
        row
        for batch in stage.result.get("batches", [])
        for row in batch.get("assessments", [])
        if row.get("candidate_id") == identifier
    ]
    assessment = assessments[-1] if assessments else None
    active = stage.status in {"queued", "running"}
    # Pre-v4 histories expose a legacy recommendation without fabricating narrative.
    legacy = next(
        (
            r
            for r in stage.result.get("recommendations", [])
            if r.get("id") == identifier
        ),
        None,
    )
    status = (
        assessment.get("assessment")
        if assessment
        else (
            "reviewing"
            if active
            else legacy.get("recommendation")
            if legacy
            else "insufficient"
        )
    )
    row = assessment or {}
    ids = list(
        dict.fromkeys(
            [
                *candidate.evidence_ids,
                *row.get("evidence_ids", []),
                *row.get("counterevidence_ids", []),
                *row.get("detail", {}).get("evidence_ids", []),
                *row.get("detail", {}).get("exploitation", {}).get("evidence_ids", []),
                *[
                    value
                    for p in row.get("premises", [])
                    for value in p.get("evidence_ids", [])
                ],
            ]
        )
    )
    return {
        "stage_id": str(stage.id),
        "stage_status": stage.status,
        "status": status,
        "evaluated": assessment is not None or legacy is not None,
        "reason": row.get("reason")
        or (
            "正在复核此候选，尚未保存结论。"
            if active
            else "历史复核已保存该结论，但没有逐项描述与项目利用用例。"
            if legacy
            else "本候选尚无通过证据校验的复核结论，不能判定真实或误报。"
        ),
        "checked_premises": row.get("checked_premises", []),
        "missing_premises": row.get("missing_premises", []),
        "runtime_unknowns": row.get("runtime_unknowns", []),
        "detail": row.get("detail"),
        "evidence_ids": ids,
        "snapshot_hash": snapshot_hash,
        "updated_at": stage.updated_at.isoformat(),
    }
