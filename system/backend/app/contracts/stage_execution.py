"""Stage defaults and request schemas, usable before database initialization."""

from pydantic import ValidationError

from app.contracts.scouting import ScoutRequest
from app.contracts.stages import RepairRequest, ReviewRequest, RuleRequest
from app.contracts.verification import SuiteGeneration
from app.domain.audit import AuditError


def default_version(kind: str) -> str:
    versions = {
        "review": "12",
        "repair": "4",
        "rule": "8",
        "scout": "7",
        "report": "5",
        "verification_suite": "2",
        "verification": "1",
        "candidate_translation": "1",
    }
    if kind not in versions:
        raise AuditError("此记录不支持后台重跑", code="conflict")
    return versions[kind]


def validate_inputs(kind: str, inputs: dict) -> dict:
    default_version(kind)
    schemas = {
        "review": ReviewRequest,
        "repair": RepairRequest,
        "rule": RuleRequest,
        "scout": ScoutRequest,
        "verification_suite": SuiteGeneration,
    }
    try:
        return (
            schemas[kind].model_validate(inputs).model_dump(mode="json")
            if kind in schemas
            else inputs
        )
    except ValidationError as exc:
        raise AuditError(str(exc), code="invalid_input") from exc
