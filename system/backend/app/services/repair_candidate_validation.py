"""Execute finite candidate checks with immutable receipts and selected-suite feedback."""

import json

from app.domain.audit import AuditError
from app.services.context_materials import digest, save_json


def validate_candidate(repair, state):
    s = repair.service
    directory = repair.directory / f"attempt-{state['attempt']}"
    from app.services.repair_integrity import validate_application

    identity = validate_application(directory, state, s.inputs)
    saved = directory / "checks.json"
    validation_receipt = directory / "validation-receipt.json"
    if saved.exists():
        checks = json.loads(saved.read_text())
        receipt = json.loads(validation_receipt.read_text())
        if receipt["identity"] != identity or receipt["checks_hash"] != digest(checks):
            raise AuditError("候选验证产物已变化")
    else:
        previous = s.directory
        try:
            s.directory = directory
            checks = s.validate(state)["checks"]
        except AuditError as exc:
            # Runtime setup failure must never become implementation feedback.
            checks = {"environment": {"status": "blocked", "output": str(exc)}}
        finally:
            s.directory = previous
        if s.stage.prompt_version == "3" and all(
            check["status"] in {"passed", "not_run"} for check in checks.values()
        ):
            from app.services.repair_consistency import check_contract

            if (
                s.inputs.verification_suite_id
                and repair.context(state).get("candidate_suite_feedback", False)
            ):
                from app.services.repair_suite_checks import check_selected_suite

                try:
                    checks["selected_suite"] = check_selected_suite(repair, state)
                except AuditError as error:
                    if error.code in {"integrity_error", "identity_error"}:
                        raise
                    checks["selected_suite"] = {
                        "status": "blocked",
                        "category": "environment",
                        "output": str(error),
                    }
            # Executed failures can drive the existing retry directly. Reserve
            # model consistency review for candidates that survive cheap checks.
            # Every accepted candidate still requires that independent review.
            if all(check["status"] in {"passed", "not_run"} for check in checks.values()):
                checks["semantic_contract"] = check_contract(repair, state)
        save_json(saved, checks)
        save_json(
            validation_receipt,
            {"identity": identity, "checks_hash": digest(checks)},
        )
    passed = all(
        v["status"] == "passed"
        or (name == "rescan" and not s.inputs.rescan and v["status"] == "not_run")
        for name, v in checks.items()
    )
    return {"checks": checks, "passed": passed}
