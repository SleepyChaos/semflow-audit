"""Source-balanced priority over immutable candidates; model truth is never a feature."""

import json
import re
from collections import defaultdict, deque
from dataclasses import dataclass
from math import isfinite
from pathlib import PurePosixPath


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
            for m in re.finditer(r"cwe-(\d+)", tag, re.IGNORECASE)
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


def _point_identity(point):
    # Preserve any path annotations supplied by a producer. Matching
    # coordinates alone cannot establish identical branch evidence.
    return json.dumps(point, sort_keys=True, separators=(",", ":"))


def _exact_alert_key(entry):
    alert = entry.get("static_alert") or {}
    paths = alert.get("code_flows", ())
    locations = alert.get("locations", ())
    # Missing path detail cannot establish duplicate path identity.
    if (
        not alert.get("rule")
        or not locations
        or not paths
        or any(len(p) < 2 for p in paths)
    ):
        return ("unclustered", entry["candidate_id"])
    return (
        alert["rule"],
        alert.get("message"),
        tuple(_point_identity(p) for p in locations),
        tuple(sorted({tuple(map(_point_identity, path)) for path in paths})),
        tuple(sorted(alert.get("tags") or ())),
        alert.get("rule_version"),
        alert.get("security_severity"),
    )


def cluster_alerts(entries):
    groups = {}
    for entry in entries:
        groups.setdefault(_exact_alert_key(entry), []).append(entry)
    return tuple(tuple(group) for group in groups.values())


@dataclass(frozen=True)
class ReviewFrontier:
    ranked: tuple[dict, ...]
    previous_ranks: dict[str, int]
    clusters: dict[str, tuple[str, ...]]


def _risk_family(entry):
    alert = entry.get("static_alert") or {}
    return alert.get("rule") or entry.get("weakness") or "unclassified"


def evidence_frontier(entries):
    """Choose auditable representatives, rotating source, family and module."""
    peers = cross_source_peers(entries)
    original = [
        e for batch in source_balanced_batches(entries, 1, peers=peers) for e in batch
    ]
    eligible = [entry for entry in original if not entry.get("source_unavailable")]
    groups = cluster_alerts(eligible)
    lanes = defaultdict(lambda: defaultdict(deque))
    for group in groups:
        entry = group[0]
        lanes[entry["origin"]][_risk_family(entry)].append(entry)
    active = deque(lanes.values())
    visited_modules = set()
    ranked = []
    while active:
        families = active.popleft()
        family = next(iter(families))
        queue = families.pop(family)
        position = next(
            (
                i
                for i, entry in enumerate(queue)
                if _module(entry) not in visited_modules
            ),
            0,
        )
        queue.rotate(-position)
        entry = queue.popleft()
        queue.rotate(position)
        visited_modules.add(_module(entry))
        ranked.append(entry)
        if queue:
            families[family] = queue
        if families:
            active.append(families)
    return ReviewFrontier(
        tuple(ranked),
        {r["candidate_id"]: i for i, r in enumerate(original, 1)},
        {
            group[0]["candidate_id"]: tuple(e["candidate_id"] for e in group)
            for group in groups
        },
    )


def _module(entry):
    return str(PurePosixPath(entry["location"]["file"]).parent)


def cluster_frontier(entries):
    original = [e for batch in source_balanced_batches(entries, 1) for e in batch]
    original_ranks = {e["candidate_id"]: i for i, e in enumerate(original, 1)}
    groups = cluster_alerts(original)
    representatives = [g[0] for g in groups]
    lanes = defaultdict(list)
    for row in representatives:
        lanes[row["origin"]].append(row)
    by_origin = deque()
    for lane in lanes.values():
        # One diversity reservation per origin, then resume severity order.
        # Repeated lower-priority families must not consume the high-risk lane.
        reserve = next(
            (
                i
                for i, row in enumerate(lane)
                if _risk_family(row) != _risk_family(lane[0])
            ),
            None,
        )
        if reserve is not None and reserve > 1:
            lane.insert(1, lane.pop(reserve))
        by_origin.append(deque(lane))
    ranked = []
    while by_origin:
        lane = by_origin.popleft()
        ranked.append(lane.popleft())
        if lane:
            by_origin.append(lane)
    return ReviewFrontier(
        tuple(ranked),
        original_ranks,
        {g[0]["candidate_id"]: tuple(e["candidate_id"] for e in g) for g in groups},
    )
