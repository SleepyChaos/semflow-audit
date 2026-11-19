"""Source-balanced priority over immutable candidates; model truth is never a feature."""

import re
from collections import defaultdict, deque
from math import isfinite


def cross_source_peers(entries):
    by_file = defaultdict(lambda: ([], []))
    for entry in entries:
        if entry["origin"] == "static":
            values = entry["static_alert"].get("tags") or ()
            lane = 0
        else:
            values = (entry.get("weakness", ""),)
            lane = 1
        cwes = {
            int(m.group(1))
            for tag in values
            for m in re.finditer(r"cwe-(\d+)", tag, re.I)
        }
        if cwes:
            by_file[entry["location"]["file"]][lane].append(
                (entry["candidate_id"], entry["location"]["line"], cwes)
            )
    peers = defaultdict(set)
    for static, scout in by_file.values():
        for left, left_line, left_cwes in static:
            for right, right_line, right_cwes in scout:
                if abs(left_line - right_line) <= 8 and left_cwes & right_cwes:
                    peers[left].add(right)
                    peers[right].add(left)
    return peers


def score_entry(entry, corroborated=False):
    if entry["origin"] != "static":
        hypothesis = entry.get("hypothesis")
        property_known = isinstance(hypothesis, dict) and bool(
            hypothesis.get("security_property")
        )
        return (
            int(property_known),
            min(len(entry.get("evidence_ids", ())), 4),
        ), "source_backed_hypothesis"
    finding = entry["static_alert"]
    try:
        severity = float(finding.get("security_severity") or 0)
    except (TypeError, ValueError):
        severity = 0
    if not isfinite(severity) or not 0 <= severity <= 10:
        severity = 0
    flow = any(len(path) > 1 for path in finding.get("code_flows", ()))
    security = severity > 0 or "security" in (finding.get("tags") or ())
    return (
        int(security),
        severity,
        int(corroborated),
        int(flow),
    ), "static_severity_and_flow"


def diverse_order(entries, peers):
    # Keep severity ordering, with one finding per file within each equal risk tier.
    by_priority = defaultdict(list)
    for entry in entries:
        score, _ = score_entry(entry, bool(peers.get(entry["candidate_id"])))
        by_priority[score].append(entry)
    result = deque()
    for priority in sorted(by_priority, reverse=True):
        hits = sorted(
            by_priority[priority],
            key=lambda r: (
                r["location"]["file"],
                r["location"]["line"],
                r["candidate_id"],
            ),
        )
        files = defaultdict(deque)
        for entry in hits:
            files[entry["location"]["file"]].append(entry)
        active = deque(files.values())
        while active:
            file = active.popleft()
            result.append(file.popleft())
            if file:
                active.append(file)
    return result


def source_balanced_batches(entries, size, *, peers=None):
    if peers is None:
        peers = cross_source_peers(entries)
    lanes = defaultdict(list)
    for entry in entries:
        lanes[entry["origin"]].append(entry)
    order = deque(
        diverse_order(lanes[name], peers) for name in ("static", "scout") if lanes[name]
    )
    batches = []
    while order:
        lane = order.popleft()
        if not batches or len(batches[-1]) == size:
            batches.append([])
        batches[-1].append(lane.popleft())
        if lane:
            order.append(lane)
    return batches
