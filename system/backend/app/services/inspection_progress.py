"""Progress feedback reuses read evidence without executing or inventing facts."""

from app.services.context_materials import digest


def existing_read(call, collected, traces, *, file_lengths=None):
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
    total = (file_lengths or {}).get(args.get("file"))
    if total is not None:
        end = min(end, total)
        if start > end:
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
        "search_contract": "Search results are navigation matches, not file bodies; read the matched source range instead of repeating search. Source window metadata gives the actual EOF; never assume more lines beyond total_lines.",
        "reused_requests": len(reused),
    }


def read_coverage(windows):
    """Union exact read ranges; a set of pages can cover a complete file."""
    files = {}
    for row in windows:
        entry = files.setdefault(
            row["file"],
            {"file": row["file"], "total_lines": row["total_lines"], "ranges": []},
        )
        entry["ranges"].append((row["start_line"], row["end_line"]))
    result = []
    for entry in files.values():
        cursor, gaps = 1, []
        for start, end in sorted(entry.pop("ranges")):
            if start > cursor:
                gaps.append({"start_line": cursor, "end_line": start - 1})
            cursor = max(cursor, end + 1)
        if cursor <= entry["total_lines"]:
            gaps.append({"start_line": cursor, "end_line": entry["total_lines"]})
        result.append({**entry, "fully_supplied": not gaps, "unread_ranges": gaps})
    return result
