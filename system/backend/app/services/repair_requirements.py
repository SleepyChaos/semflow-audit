"""Carry user-selected acceptance requirements into repair without test execution."""

from app.domain.audit import AuditError


def acceptance_contract(service):
    identifier = service.inputs.verification_suite_id
    if not identifier:
        return None
    from app.services.verification_suites import read_suite, target_ids

    stage, suite, _ = read_suite(identifier, service.stage.audit_id)
    targets = set(map(str, service.inputs.candidate_ids))
    if not targets.issubset(target_ids(suite)):
        raise AuditError("所选验收要求未覆盖当前修复目标")
    return {
        "suite_id": str(stage.id),
        "suite_hash": stage.result["suite_hash"],
        "image": stage.result["image"],
        "requirements": stage.inputs.get("requirements", ""),
        "cases": [
            {
                "name": case.name,
                "category": case.category,
                "input_description": case.input_description,
                "expected_behavior": case.expected_behavior,
            }
            for case in suite.cases
            if case.category == "functional"
            or targets.intersection(map(str, case.candidate_ids))
        ],
        "meaning": "User-selected acceptance expectations, not source evidence or proof of safety. Test code and hidden benchmark oracles are not supplied. The unchanged suite runs separately after patch generation.",
    }


def request_materials(evidence, descriptions, acceptance=None):
    """Record confirmed intent separately; it never proves actual code behavior."""
    import json

    rows = [
        evidence.record(
            "repair_request",
            json.dumps(description, ensure_ascii=False, sort_keys=True),
            {
                "candidate_id": description["id"],
                "meaning": "Confirmed repair intent only; not source behavior or security proof",
            },
        )
        for description in descriptions
    ]

    if acceptance is not None:
        rows.append(
            evidence.record(
                "repair_request",
                json.dumps(acceptance, ensure_ascii=False, sort_keys=True),
                {
                    "suite_id": acceptance["suite_id"],
                    "suite_hash": acceptance["suite_hash"],
                    "meaning": "User-selected acceptance intent only, not executed proof",
                },
            )
        )
    return rows
