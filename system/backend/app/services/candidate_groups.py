"""Evidence-backed issue projections; source candidates and stage IDs stay intact."""

import copy
import hashlib
import posixpath
import re
from itertools import combinations
from types import SimpleNamespace

from app.adapters.operation_evidence import locate_quote
from app.domain.audit import AuditError


def rank(row):
    classification, review = row.get("classification") or {}, row.get("review") or {}
    return (
        classification.get("source") == "human",
        classification.get("updated_at", "") or "",
        bool(review.get("evaluated")),
        review.get("updated_at", "") or row.get("created_at", ""),
        row.get("origin") == "static",
        row["id"],
    )


def location_key(row):
    location = row.get("location", {})
    file, line = location.get("file"), location.get("line")
    if not file or not isinstance(line, int) or line < 1:
        return None
    return posixpath.normpath(file.replace("\\", "/")), line


def weakness_family(row):
    value = re.fullmatch(r"CWE-0*(\d+)", row.get("weakness", ""), re.I)
    number = int(value[1]) if value else None
    return 94 if number in {94, 95} else number


def source_quote(row):
    review = row.get("review") or {}
    example = (review.get("detail") or {}).get("exploitation") or {}
    return " ".join(example.get("source_quote", "").split())


def quoted_location(row, evidence, snapshot_hash, language):
    location = location_key(row)
    review = row.get("review") or {}
    if not location or not source_quote(row) or not review.get("evaluated"):
        return location
    material = [
        e
        for e in evidence
        if e.get("snapshot_hash") == snapshot_hash
        and e.get("audit_id") == row["audit_id"]
    ]
    clue = SimpleNamespace(
        primary_location=SimpleNamespace(file=location[0], line=location[1]),
        operation_quote=source_quote(row),
        evidence_ids=review.get("evidence_ids", row.get("evidence_ids", [])),
    )
    try:
        found = locate_quote(
            clue, {"snapshot": snapshot_hash, "evidence": material}, language
        )
    except AuditError:
        return location
    return found["file"], found["line"]


def project_candidates(rows, stages, snapshot_hash, evidence=(), language="python"):
    """Collapse reviewed duplicates, with explicit conflicts kept visible."""
    if not rows:
        return []
    by_id = {row["id"]: row for row in rows}
    parents = {identifier: identifier for identifier in by_id}
    forbidden, relations = set(), []

    def find(identifier):
        while parents[identifier] != identifier:
            identifier = parents[identifier]
        return identifier

    def join(a, b):
        left, right = find(a), find(b)
        if left == right:
            return
        members_a = [i for i in parents if find(i) == left]
        members_b = [i for i in parents if find(i) == right]
        if any(frozenset((x, y)) in forbidden for x in members_a for y in members_b):
            return
        parents[right] = left

    # First retain one lineage for retries; no physical-location guessing here.
    identities = {}
    for row in rows:
        key = row["audit_id"], row.get("identity_key") or row["id"]
        previous = identities.get(key)
        if previous:
            join(previous["id"], row["id"])
        if previous is None or rank(row) > rank(previous):
            identities[key] = row
    current = list(identities.values())
    current_ids = {row["id"] for row in current}
    anchors = {
        row["id"]: quoted_location(row, evidence, snapshot_hash, language)
        for row in current
    }

    for stage in stages:
        result = stage.result
        if stage.kind != "review" or stage.status != "completed":
            continue
        if (
            result.get("snapshot_hash", result.get("pool", {}).get("snapshot"))
            != snapshot_hash
        ):
            continue
        for relation in result.get("root_relations", []):
            ids = [i for i in relation["candidate_ids"] if i in current_ids]
            for a, b in combinations(ids, 2):
                if by_id[a]["audit_id"] != str(stage.audit_id) or by_id[b][
                    "audit_id"
                ] != str(stage.audit_id):
                    continue
                if relation["relationship"] in {"distinct", "related"}:
                    forbidden.add(frozenset((a, b)))
                elif relation["relationship"] == "same_root_cause" and relation.get(
                    "evidence_ids"
                ):
                    relations.append((a, b))

    for a, b in relations:
        left, right = by_id[a], by_id[b]
        reviews = [row.get("review") or {} for row in (left, right)]
        columns = {
            r["location"].get("column")
            for r in (left, right)
            if r["location"].get("column")
        }
        if (
            anchors[a]
            and anchors[a] == anchors[b]
            and weakness_family(left) is not None
            and weakness_family(left) == weakness_family(right)
            and source_quote(left)
            and source_quote(left) == source_quote(right)
            and len(columns) <= 1
            and all(
                r.get("evaluated") and r.get("snapshot_hash") == snapshot_hash
                for r in reviews
            )
        ):
            join(a, b)

    locations = {}
    for row in current:
        review = row.get("review") or {}
        key = anchors[row["id"]]
        if (
            not key
            or not review.get("evaluated")
            or review.get("snapshot_hash") != snapshot_hash
        ):
            continue
        locations.setdefault((row["audit_id"], key, weakness_family(row)), []).append(
            row
        )
    for (*_, weakness), group in locations.items():
        columns = {
            r["location"].get("column") for r in group if r["location"].get("column")
        }
        quotes = {source_quote(row) for row in group}
        if (
            weakness is None
            or len(columns) > 1
            or len(quotes) != 1
            or not next(iter(quotes))
        ):
            continue
        for row in group[1:]:
            # A shifted primary location also needs the saved same-root review
            # relation above: a shared input quote alone does not identify a sink.
            if location_key(group[0]) == location_key(row):
                join(group[0]["id"], row["id"])

    groups = {}
    for row in rows:
        groups.setdefault(find(row["id"]), []).append(row)
    return [present_group(group, current_ids) for group in groups.values()]


def present_group(group, current_ids):
    current = [row for row in group if row["id"] in current_ids]
    canonical = max(current, key=rank)
    result = copy.deepcopy(canonical)
    evidence_ids = list(
        dict.fromkeys(
            identifier
            for row in current
            for identifier in [
                *row.get("evidence_ids", []),
                *(row.get("review") or {}).get("evidence_ids", []),
            ]
        )
    )
    statuses = {
        (row.get("classification") or {}).get("status", row["status"])
        for row in current
    }
    conflict = (
        len(statuses) > 1
        and (canonical.get("classification") or {}).get("source") != "human"
    )
    lineage = sorted({row.get("identity_key") or row["id"] for row in group})
    identity = f"{canonical['audit_id']}:{'|'.join(lineage)}"
    result["issue"] = {
        "key": hashlib.sha256(identity.encode()).hexdigest(),
        "canonical_id": canonical["id"],
        "member_ids": [row["id"] for row in group],
        "current_ids": [row["id"] for row in current],
        "origins": sorted({row["origin"] for row in current}),
        "evidence_ids": evidence_ids,
        "conflict": conflict,
        "sources": [
            {
                "id": row["id"],
                "origin": row["origin"],
                "static_finding_id": row.get("static_finding_id"),
                "classification": row.get("classification"),
                "review": row.get("review"),
            }
            for row in current
        ],
    }
    result["evidence_ids"] = evidence_ids
    if conflict:
        result["status"] = "insufficient"
        result["classification"] = {"status": "insufficient", "source": "pending"}
    return result
