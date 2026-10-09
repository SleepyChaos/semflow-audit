"""Scope-checked paged source reads and recoverable tool observations."""

import json

from app.services.read_tools import observe_tool, reused_read, window_observations
from app.services.review import ReviewService

SOURCE_TOOL_CONTRACT = {
    "read_source": {
        "max_lines": 151,
        "start_line_min": 1,
        "pagination": "Large requests return the first page and next_start_line; request remaining pages explicitly",
    },
    "security": "Scope/path violations are rejected; parameter errors never imply safe source",
}


def prime_source_pages(evidence, materials, entries, include_related=False):
    """Read small target modules once; no whole-project completeness claim."""
    collected = list(materials)
    from app.adapters.source_inventory import inspectable

    files = {r["location"]["file"] for r in entries}
    if include_related:
        files |= {
            r["reference"]["file"]
            for r in materials
            if r["kind"] == "code"
            and inspectable(r["reference"].get("file", ""), evidence.audit.language)
        }
    for file in sorted(files):
        path = evidence.allowed(file)
        if path.stat().st_size > 16000:
            continue
        lines = path.read_text().splitlines()
        if len(lines) > 350 or any(len(line) > 10000 for line in lines):
            continue
        pages, start = [], 1
        while start <= len(lines):
            end = min(start + 150, len(lines))
            while len("\n".join(lines[start - 1 : end])) > 10000:
                end -= 1
            pages.append(evidence.read(file, start, end))
            start = end + 1
        candidate = [
            r
            for r in collected
            if not (r["kind"] == "code" and r["reference"].get("file") == file)
        ] + pages
        if len(json.dumps(candidate, ensure_ascii=False)) <= 23000:
            collected = candidate
    return list({r["id"]: r for r in collected}.values())


def gather_review_tool(service, context, call):
    requested = call
    pagination = None
    if call["name"] == "read_source":
        args = dict(call["arguments"])
        # Validate scope before adapting any requested source coordinates.
        path = service.evidence.allowed(args.get("file", ""))
        start, end = args.get("start_line", 1), args.get("end_line", 60)
        total = len(path.read_text().splitlines())
        if (
            type(start) is not int
            or type(end) is not int
            or start < 1
            or end < start
            or start > total
        ):
            return {
                **context,
                "latest_tool_observation": {
                    "status": "invalid_arguments",
                    "requested": requested,
                    "total_lines": total,
                    "max_lines": 151,
                    "instruction": "Correct coordinates within this file; no source was read",
                },
                "server_feedback": "Read parameter error is recoverable; request a legal window or return insufficient",
            }
        actual_end = min(end, start + 150, total)
        lines = path.read_text().splitlines()
        while (
            actual_end >= start
            and len("\n".join(lines[start - 1 : actual_end])) > 10000
        ):
            actual_end -= 1
        if actual_end < start:
            return {
                **context,
                "latest_tool_observation": {
                    "status": "oversized_source_line",
                    "file": args["file"],
                    "line": start,
                    "instruction": "This line cannot fit the source tool; retain an explicit evidence gap, do not infer safe behavior",
                },
            }
        args.update(start_line=start, end_line=actual_end)
        call = {"name": "read_source", "arguments": args}
        pagination = {
            "requested": requested["arguments"],
            "returned": args,
            "total_lines": total,
            "complete_requested_range": actual_end >= min(end, total),
            "next_start_line": actual_end + 1 if actual_end < min(end, total) else None,
        }
    previous = reused_read(context, call)
    if previous is not None:
        context = observe_tool(context, call, previous, reused=True)
    else:
        context = ReviewService.gather(
            service, {"context": context, "response": {"tool": call}}
        )["context"]
        data = next(
            r
            for r in context["evidence"]
            if r["id"] == context["tool_trace"][-1]["evidence_id"]
        )
        context["tool_trace"] = context["tool_trace"][:-1]
        context = observe_tool(context, call, data)
    if pagination is not None:
        context["latest_tool_observation"]["pagination"] = pagination
    context["source_windows"] = window_observations(
        service.evidence, context["evidence"]
    )
    return context
