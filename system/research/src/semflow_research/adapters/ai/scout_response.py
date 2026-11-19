"""Recover only length overflow in Scout's explanatory display fields."""

import json

from pydantic import ValidationError


def recover_display_fields(content, schema, error):
    violations = error.errors(include_input=False, include_url=False)
    if not violations or any(
        row["type"] != "string_too_long"
        or len(row["loc"]) != 3
        or row["loc"][0] != "task_checks"
        or not isinstance(row["loc"][1], int)
        or row["loc"][2] != "reason"
        or not isinstance(row.get("ctx", {}).get("max_length"), int)
        for row in violations
    ):
        return None
    try:
        value = json.loads(content)
        for row in violations:
            reason = value["task_checks"][row["loc"][1]]
            limit = row["ctx"]["max_length"]
            if not isinstance(reason["reason"], str) or limit < 10:
                return None
            reason["reason"] = reason["reason"][: limit - 1].rstrip() + "…"
        return schema.model_validate(value)
    except (ValidationError, ValueError, TypeError, KeyError, IndexError):
        return None
