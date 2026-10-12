"""Progress feedback reuses read evidence without executing or inventing facts."""

from app.services.context_materials import digest


def existing_read(call, collected, traces):
    for trace in traces:
        if (trace["name"], trace["arguments"]) == (call["name"], call["arguments"]):
            return next(row for row in collected if row["id"] == trace["evidence_id"])
    if call["name"] not in {"read_source", "read_document"}:
        return None
    args = call["arguments"]
    if set(args) - {"file", "start_line", "end_line"}:
        return None
    start, end = args.get("start_line", 1), args.get("end_line", 80)
    if (
        not isinstance(start, int)
        or not isinstance(end, int)
        or start < 1
        or end < start
    ):
        return None
    for row in collected:
        ref = row["reference"]
        if (
            row["kind"] == "code"
            and ref.get("file") == args.get("file")
            and ref.get("start_line", 0) <= start
            and ref.get("end_line", 0) >= end
        ):
            return row
    return None


def stable_evidence(rows):
    # Keep the first ID: supported facts must not lose their citations after a reread.
    result, seen = [], set()
    for row in rows:
        identity = digest({"reference": row["reference"], "digest": row["digest"]})
        if identity not in seen:
            result.append(row)
            seen.add(identity)
    return result


def progress_feedback(original, traces):
    reused = [trace for trace in traces if trace.get("reused")]
    return {
        "validation_feedback": original,
        "latest_observation": traces[-1] if traces else None,
        "instruction": "Evidence contains exact read bodies. Reuse their existing IDs. Do not reread a supplied window. If evidence suffices return ready; otherwise name a NEW missing fact and read only its absent source/document. Never infer safety from budget exhaustion.",
        "reused_requests": len(reused),
    }
