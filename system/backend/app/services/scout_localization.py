"""Source-grounded localization feedback; no guessed API or automatic ambiguity choice."""

from app.adapters.operation_evidence import normalize


def localization_feedback(rejected, context):
    repairs = []
    for failure in rejected:
        if failure.get("code") != "operation_ambiguous":
            continue
        row = failure["hypothesis"]
        supplied = set(row["evidence_ids"])
        matches = {}
        for material in context["evidence"]:
            ref = material["reference"]
            if (
                material["id"] not in supplied
                or material["kind"] != "code"
                or ref.get("file") != row["primary_location"]["file"]
            ):
                continue
            lines = material["content"].splitlines()
            for offset, line in enumerate(lines):
                if normalize(row["operation_quote"]) not in normalize(line):
                    continue
                actual = ref["start_line"] + offset
                start, end = max(0, offset - 1), min(len(lines), offset + 2)
                matches[actual] = {
                    "evidence_id": material["id"],
                    "line": actual,
                    "numbered_source": "\n".join(
                        f"{ref['start_line'] + n}: {lines[n]}"
                        for n in range(start, end)
                    ),
                }
        repairs.append(
            {
                "proposal": row,
                "reason": failure["reason"],
                "actual_occurrences": list(matches.values())[:12],
            }
        )
    if not repairs:
        return None
    return {
        "status": "one_bounded_localization_retry",
        "instruction": "The host did not choose among repeated source statements. Correct only ambiguous proposals using exact supplied occurrences/branch context. Return final with precise line/unique quote, or omit and leave that task unknown. Previously accepted findings are preserved by the host. These excerpts are actual already-cited source, not new evidence or vulnerability confirmations.",
        "repairs": repairs[:6],
    }


def merge_findings(previous, current):
    """Retain already grounded observations even if the repair omits them."""
    rows = {}
    for row in [*previous, *current]:
        key = (
            row.primary_location.file,
            row.primary_location.line,
            row.security_property,
        )
        rows[key] = row
    return list(rows.values())[:16]
