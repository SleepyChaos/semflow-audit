"""Trace raw candidate identities to review decisions and score allocation."""

from scripts.benchmarks.realvuln_ablation_io import findings


def transitions(project, root, raw, review, scored, evaluator, gold, source):
    before_alloc, before_compatible = scored["C"][2:]
    after_alloc = scored["F"][2]
    candidates = review["candidates"]
    linked = {}
    identity = {c["identity_key"]: c for c in candidates}
    assessments = {}
    rejected, batches = {}, {}
    for batch in review["stage"]["result"].get("batches", []):
        for identifier in batch.get("candidate_ids", []):
            batches.setdefault(identifier, []).append(
                {k: batch.get(k) for k in ("batch_id", "status", "reason", "code")}
            )
        for item in batch.get("assessments", []):
            assessments[item["candidate_id"]] = item
        for item in batch.get("rejected_assessments", []):
            rejected.setdefault(item["candidate_id"], []).append(
                {
                    **{k: item.get(k) for k in ("reason", "code")},
                    "proposed_verdict": item.get("assessment", {}).get("assessment"),
                    "proposed_evidence_ids": item.get("assessment", {}).get(
                        "evidence_ids", []
                    ),
                }
            )
    for c in candidates:
        if c.get("static_finding_id"):
            linked[c["static_finding_id"]] = c
        elif c.get("related_target"):
            linked[c["related_target"]] = c
    rows, used = [], set()
    static_weaknesses = {
        r["id"]: r["weaknesses"] for r in raw if r["source"] == "codeql"
    }
    scored_before = {}
    for match in evaluator.match(findings(raw, "C", source), gold):
        finding = match.scanner_finding
        if finding is not None:
            scored_before.setdefault(finding.finding_id, []).append(
                {
                    "cwe": finding.cwe,
                    "classification": match.classification,
                    "gold_id": match.ground_truth_id,
                }
            )
    for before in raw:
        after = linked.get(before["id"])
        deduplicated = False
        if after is None and before.get("identity_key") in identity:
            after, deduplicated = identity[before["identity_key"]], True
        assessment = assessments.get(after["id"], {}) if after else {}
        if after:
            used.add(after["id"])
        before_set = before_compatible.get(before["id"], [])
        after_set = []
        after_cwes = []
        if after:
            after_cwes = [after["weakness"]]
            if (
                after["weakness"] == "unknown"
                and after.get("static_finding_id") in static_weaknesses
            ):
                after_cwes = static_weaknesses[after["static_finding_id"]]
            fs = findings([{**after, "weaknesses": after_cwes}], "transition", source)
            _, _, _, compatible = evaluator.score(project, "transition", fs, gold)
            after_set = compatible.get(after["id"], [])
        rows.append(
            {
                "group": "F",
                "project_id": project,
                "candidate_id": before["id"],
                "original_candidate_id": before.get(
                    "original_candidate_id", before["id"]
                ),
                "source": before["source"],
                "review_candidate_id": after["id"] if after else None,
                "review_state": after["model_assessment"]
                if after
                else "unknown_not_entered",
                "before_allocated_gold_ids": before_alloc.get(before["id"], []),
                "before_scored_entities": scored_before.get(before["id"], []),
                "after_supported_allocated_gold_ids": after_alloc.get(after["id"], [])
                if after
                else [],
                "before_compatible_gold_ids": before_set,
                "after_compatible_gold_ids": after_set,
                "before_location": before["location"],
                "after_location": after["location"] if after else {},
                "before_cwes": before["weaknesses"],
                "after_cwe": after["weakness"] if after else None,
                "after_scored_cwes": after_cwes,
                "location_changed": bool(
                    after and before["location"] != after["location"]
                ),
                "cwe_changed": bool(
                    after and after["weakness"] not in before["weaknesses"]
                ),
                "deduplicated_by_identity": deduplicated,
                "evidence_ids": after["evidence_ids"] if after else [],
                "reason": assessment.get("reason"),
                "missing_premises": assessment.get("missing_premises", []),
                "rejected_verdicts": rejected.get(after["id"], []) if after else [],
                "batch_execution": batches.get(after["id"], []) if after else [],
                "stop_reason": review["stage"].get("error")
                or review["stage"]["result"].get("stop_reason"),
                "receipt": str(root / "system" / project / "review.json"),
            }
        )
    for c in candidates:
        if c["id"] not in used:
            rows.append(
                {
                    "group": "F",
                    "project_id": project,
                    "candidate_id": c["id"],
                    "source": "review_new_or_unlinked",
                    "review_candidate_id": c["id"],
                    "review_state": c["model_assessment"],
                    "after_supported_allocated_gold_ids": after_alloc.get(c["id"], []),
                    "evidence_ids": c["evidence_ids"],
                }
            )
    return rows
