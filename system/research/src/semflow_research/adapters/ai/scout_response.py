"""Recover only length overflow in Scout's explanatory display fields."""

import json
from dataclasses import dataclass

from pydantic import ValidationError


@dataclass(frozen=True)
class ScoutFormatRecovery:
    response: object
    edits: tuple[dict, ...]

    @property
    def classification(self) -> str:
        kinds = {edit["kind"] for edit in self.edits}
        if "invalid_finding" in kinds:
            return "revalidated_partial_findings"
        if kinds == {"exact_enum_alias"}:
            return "revalidated_exact_alias"
        if kinds == {"display_length"}:
            return "revalidated_display_fields"
        return "revalidated_mixed_format"


# These are exact conclusion literals misplaced in the status slot, never
# model-specific synonyms. The source/citation validator still has to accept them.
_CONCLUSION_ALIASES = {
    "suspicious": "investigated",
    "no_condition_identified": "investigated",
}


def recover_scout_format(content, schema, error, *, isolate_findings=False):
    violations = error.errors(include_input=False, include_url=False)
    try:
        value = json.loads(content)
        edits, bad_findings = [], {}
        for row in violations:
            path = row["loc"]
            if (
                isolate_findings
                and value.get("action") == "final"
                and len(path) >= 2
                and path[0] == "findings"
                and isinstance(path[1], int)
            ):
                bad_findings.setdefault(path[1], []).append(
                    {"field": list(path[2:]), "code": row["type"]}
                )
                continue
            if (
                len(path) != 3
                or path[0] != "task_checks"
                or not isinstance(path[1], int)
            ):
                return None
            check = value["task_checks"][path[1]]
            if path[2] == "status" and row["type"] == "literal_error":
                alias = check["status"]
                canonical = _CONCLUSION_ALIASES.get(alias)
                if canonical is None or check.get("conclusion") != alias:
                    return None
                check["status"] = canonical
                edits.append(
                    {
                        "path": list(path),
                        "kind": "exact_enum_alias",
                        "before": alias,
                        "after": canonical,
                    }
                )
            elif path[2] == "reason" and row["type"] == "string_too_long":
                limit = row.get("ctx", {}).get("max_length")
                if not isinstance(limit, int) or limit < 10:
                    return None
                before = len(check["reason"])
                check["reason"] = check["reason"][: limit - 1].rstrip() + "…"
                edits.append(
                    {
                        "path": list(path),
                        "kind": "display_length",
                        "characters_before": before,
                        "characters_after": len(check["reason"]),
                    }
                )
            else:
                # Observation, citations, missing facts and candidate meaning
                # are left intact; these need a new response rather than edits.
                return None
        if bad_findings:
            findings = value["findings"]
            if len(bad_findings) >= len(findings):
                return None
            value["findings"] = [
                finding
                for index, finding in enumerate(findings)
                if index not in bad_findings
            ]
            edits.extend(
                {
                    "path": ["findings", index],
                    "kind": "invalid_finding",
                    "errors": errors,
                }
                for index, errors in bad_findings.items()
            )
        return (
            ScoutFormatRecovery(schema.model_validate(value), tuple(edits))
            if edits
            else None
        )
    except (ValueError, TypeError, AttributeError, KeyError, IndexError):
        return None


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
