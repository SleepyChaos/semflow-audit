"""Algorithm extracted from app.services.repair_candidate_validation.

Runtime dependencies are passed explicitly; no platform ORM or configuration.
Changes to JSON require checking the corresponding semflow_contracts/wire peer.
"""

"""Execute finite candidate checks with immutable receipts and selected-suite feedback."""
import json

from semflow_research.domain.errors import AuditError
from semflow_research.evidence.context_materials import digest, save_json


def validate_candidate(repair, state, *, _kernel):
    s = repair.service
    directory = repair.directory / f"attempt-{state['attempt']}"
    from semflow_research.repair.repair_integrity import validate_application

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
            checks = {"environment": {"status": "blocked", "output": str(exc)}}
        finally:
            s.directory = previous
        if s.execution.method_version in {"3", "4"} and all(
            check["status"] in {"passed", "not_run"} for check in checks.values()
        ):
            from semflow_research.repair.repair_consistency import check_contract

            if s.inputs.verification_suite_id and repair.context(state).get(
                "candidate_suite_feedback", False
            ):
                from semflow_research.repair.repair_suite_checks import (
                    check_selected_suite,
                )

                try:
                    checks["selected_suite"] = check_selected_suite(
                        repair, state, _kernel=_kernel
                    )
                except AuditError as error:
                    if error.code in {"integrity_error", "identity_error"}:
                        raise
                    checks["selected_suite"] = {
                        "status": "blocked",
                        "category": "environment",
                        "output": str(error),
                    }
            if (
                _kernel.spec.inputs.method_policy.feedback_policy.semantic_consistency
                and all(
                    check["status"] in {"passed", "not_run"}
                    for check in checks.values()
                )
            ):
                checks["semantic_contract"] = check_contract(
                    repair, state, _kernel=_kernel
                )
        save_json(saved, checks)
        save_json(
            validation_receipt, {"identity": identity, "checks_hash": digest(checks)}
        )
    executed = [
        value
        for name, value in checks.items()
        if not (name == "rescan" and not s.inputs.rescan)
    ]
    passed = bool(executed) and all(
        (
            v["status"] == "passed"
            or (
                name == "rescan"
                and (not s.inputs.rescan)
                and (v["status"] == "not_run")
            )
            for name, v in checks.items()
        )
    )
    return {"checks": checks, "passed": passed}
