"""Keep every selected repair request in the evidence-grounded interpretation."""

from app.domain.audit import AuditError


def missing_targets(inspection, targets):
    cited = {
        identifier
        for fact in inspection["view"]["facts"]
        if fact["state"] == "supported"
        for identifier in fact["evidence_ids"]
    }
    covered = {
        row["reference"].get("candidate_id")
        for row in inspection["evidence"]
        if row["kind"] == "repair_request" and row["id"] in cited
    }
    return [target for target in targets if target["id"] not in covered]


def complete_target_scope(reader, inspection, targets, **arguments):
    missing = missing_targets(inspection, targets)
    if missing:
        inspection = reader.inspect(
            targets,
            inspection["evidence"],
            namespace=arguments.pop("namespace", "initial") + "-target-coverage",
            feedback={
                "missing_repair_targets": missing,
                "instruction": (
                    "All supplied targets are explicitly selected repair requests. "
                    "Do not reduce the batch to its first item or describe other selected "
                    "targets as unrelated/out of scope. Ground the repair intent for every "
                    "target in its repair_request evidence, and the actual implementation "
                    "in source evidence. Return the complete joint interpretation. "
                    "Use insufficient for unresolved constraints; never silently omit a target."
                ),
            },
            **arguments,
        )
    if missing_targets(inspection, targets):
        raise AuditError(
            "批量修复语义未覆盖全部已选漏洞，未将部分补丁标为全部完成",
            code="repair_scope_incomplete",
        )
    return inspection
