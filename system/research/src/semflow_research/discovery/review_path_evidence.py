"""Read bounded source around static path locations, with no behavioral inference."""

import json
from collections import deque

from semflow_research.domain.errors import AuditError
from semflow_research.evidence.read_tools import grounded


def missing_path_points(entry, pages):
    alert = entry.get("static_alert") or {}
    emitted = set()
    # Each reported path retains its ordered endpoints. Distinct paths are not
    # combined into a synthetic flow.
    for path in alert.get("code_flows", ()):
        for index, value in enumerate(path):
            file, line = value.get("file"), value.get("line")
            if not file or type(line) is not int or line < 1:
                continue
            point = {"file": file, "line": line}
            key = (file, line)
            if key in emitted or grounded(pages, point):
                continue
            emitted.add(key)
            yield {
                **point,
                "path_role": "source"
                if index == 0
                else "sink"
                if index == len(path) - 1
                else "propagation",
            }


def prime_linked_pages(evidence, entries, pages, *, max_chars, max_pages=3):
    initial = list(pages)
    queued = deque(
        (entry["candidate_id"], iter(missing_path_points(entry, initial)))
        for entry in entries
        if entry.get("static_alert")
    )
    additions = []
    attempts = 0
    while queued and len(additions) < max_pages and attempts < max_pages * 4:
        identifier, points = queued.popleft()
        point = next(points, None)
        if point is None:
            continue
        queued.append((identifier, points))
        if grounded(pages, point):
            continue
        attempts += 1
        try:
            page = evidence.read(
                point["file"], max(1, point["line"] - 4), point["line"] + 8
            )
        except AuditError as exc:
            if exc.code in {"integrity_error", "identity_error"}:
                raise
            continue
        except (OSError, UnicodeError):
            continue
        if len(json.dumps([*pages, page], ensure_ascii=False)) > max_chars:
            continue
        pages = [*pages, page]
        additions.append(
            {"candidate_id": identifier, **point, "evidence_id": page["id"]}
        )
    return pages, additions
