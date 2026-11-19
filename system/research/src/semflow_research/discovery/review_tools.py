"""Algorithm extracted from app.services.review_tools.

Runtime dependencies are passed explicitly; no platform ORM or configuration.
Changes to JSON require checking the corresponding semflow_contracts/wire peer.
"""

"""Scope-checked paged source reads and recoverable tool observations."""
import json

from semflow_research.adapters.source_text import read_source_text

from semflow_research.discovery.review import ReviewService
from semflow_research.domain.errors import AuditError
from semflow_research.evidence.read_tools import (
    observe_tool,
    reused_read,
    window_observations,
)

SOURCE_TOOL_CONTRACT = {
    "read_source": {
        "max_lines": 151,
        "start_line_min": 1,
        "pagination": "Large requests return the first page and next_start_line; request remaining pages explicitly",
    },
    "security": "Scope/path violations are rejected; parameter errors never imply safe source",
}


def prime_source_pages(
    evidence, materials, entries, include_related=False, *, max_evidence_chars=23000
):
    """Read small target modules once; no whole-project completeness claim."""
    collected = list(materials)
    from semflow_research.adapters.source_inventory import inspectable

    files = {r["location"]["file"] for r in entries}
    if include_related:
        files |= {
            r["reference"]["file"]
            for r in materials
            if r["kind"] == "code"
            and inspectable(
                r["reference"].get("file", ""), evidence.source_context.language
            )
        }
    for file in sorted(files):
        path = evidence.allowed(file)
        if path.stat().st_size > 16000:
            continue
        lines = read_source_text(path).splitlines()
        if len(lines) > 350 or any(len(line) > 10000 for line in lines):
            continue
        pages, start = ([], 1)
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
        if len(json.dumps(candidate, ensure_ascii=False)) <= max_evidence_chars:
            collected = candidate
    return list({r["id"]: r for r in collected}.values())


def gather_review_tool(service, context, call, *, _kernel):
    requested = call
    pagination = None
    if service.evidence.repository_navigation and call["name"] == "search_source":
        args = call["arguments"]
        text = args.get("text")
        file_pattern = args.get("file_pattern")
        if (
            not isinstance(text, str)
            or not text
            or len(text) > 200
            or (
                file_pattern is not None
                and (not isinstance(file_pattern, str) or len(file_pattern) > 200)
            )
            or set(args) - {"text", "file_pattern"}
        ):
            return {
                **context,
                "latest_tool_observation": {
                    "status": "invalid_arguments",
                    "requested": requested,
                    "instruction": "Use search_source with text and optional file_pattern.",
                },
            }
    if call["name"] == "read_source":
        args = dict(call["arguments"])
        try:
            path = service.evidence.allowed(args.get("file", ""))
            if (
                service.evidence.repository_navigation
                and path.stat().st_size > 1024 * 1024
            ):
                raise AuditError("文件超过源码读取上限", code="source_size")
            lines = read_source_text(path).splitlines()
        except (AuditError, OSError, UnicodeError, TypeError) as error:
            if not service.evidence.repository_navigation or getattr(
                error, "code", None
            ) in {"identity_error", "integrity_error"}:
                raise
            return _unavailable_source(
                service, context, requested, args.get("file"), error
            )
        start, end = (args.get("start_line", 1), args.get("end_line", 60))
        total = len(lines)
        if (
            type(start) is not int
            or type(end) is not int
            or start < 1
            or (end < start)
            or (start > total)
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
        args = (
            {"file": args["file"], "start_line": start, "end_line": actual_end}
            if service.evidence.repository_navigation
            else {**args, "start_line": start, "end_line": actual_end}
        )
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


def _unavailable_source(service, context, requested, file, error):
    from semflow_research.adapters.repository_locator import RepositoryLocator

    locator = RepositoryLocator(service.evidence.root, service.evidence.allowed)
    paths = locator.find_paths(file, limit=3).matches if isinstance(file, str) else ()
    return {
        **context,
        "latest_tool_observation": {
            "requested": requested,
            "status": "unavailable",
            "reason": getattr(error, "code", "source_unavailable"),
            "relative_path_matches": [match.file for match in paths],
            "instruction": (
                "No source was read. Use a checked relative path, search for the symbol, "
                "or return an evidence gap naming its symbol."
            ),
        },
    }
