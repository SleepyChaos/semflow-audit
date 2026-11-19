"""Convert accepted review gaps into bounded, source-backed navigation."""

import re
from dataclasses import dataclass
from hashlib import sha256
from uuid import UUID

from semflow_contracts.review_gaps import EvidenceGapRequest, ReviewEvidenceGap
from semflow_contracts.review_handoff import ReviewSourceWindow

from semflow_research.adapters.repository_locator import RepositoryLocator
from semflow_research.adapters.review_evidence import missing_source_paths
from semflow_research.domain.errors import AuditError

from semflow_research.adapters.source_text import read_source_text

_SYMBOL = re.compile(r"\b([A-Za-z_$][A-Za-z0-9_$]{1,79})\s*\(")
_MAX_REQUESTS = 5
_MAX_WINDOWS = 3


def navigation_enabled(kernel) -> bool:
    spec = getattr(kernel, "spec", None)
    return (
        getattr(spec, "operation", None) == "review"
        and spec.implementation.method_version == "12"
        and getattr(spec.inputs.policy, "version", None)
        in {"2", "2-no-cache", "3", "3-no-cache", "4", "4-no-cache"}
    )


def obligations_enabled(kernel) -> bool:
    return navigation_enabled(kernel) and kernel.spec.inputs.policy.version in {
        "3",
        "3-no-cache",
        "4",
        "4-no-cache",
    }


@dataclass(frozen=True)
class GapPlan:
    gaps: tuple[ReviewEvidenceGap, ...]
    windows: tuple[tuple[str, ReviewSourceWindow], ...]


def plan_gaps(
    assessment: dict, evidence, seen, prior=(), *, host_navigation=False
) -> GapPlan:
    candidate_id = assessment.get("candidate_id")
    if not candidate_id or assessment.get("assessment") not in {
        "insufficient",
        "pending",
    }:
        return GapPlan((), ())
    locator = RepositoryLocator(evidence.root, evidence.allowed)
    previous = {gap.gap_id: gap for gap in prior}
    records, windows = {}, []
    requests = _requests(assessment, host_navigation)
    for request in requests:
        gap = _record(
            UUID(candidate_id), request, evidence.source_context.snapshot_hash
        )
        if gap.gap_id in records:
            continue
        old = previous.get(gap.gap_id)
        if (
            old
            and old.status in {"found", "not_found", "blocked", "exhausted"}
            and old.attempt_count
        ):
            records[gap.gap_id] = old
            continue
        if request.gap_type != "repository":
            records[gap.gap_id] = gap
            continue
        if len(windows) >= _MAX_WINDOWS:
            records[gap.gap_id] = gap.model_copy(
                update={"status": "exhausted", "failure_reason": "source_window_budget"}
            )
            continue
        result = _locate(locator, request)
        new = []
        covered = (*seen, *(window for _, window in windows))
        for hit in result.matches:
            window = _unread(
                evidence, hit.file, hit.start_line, hit.end_line, covered, hit.kind
            )
            if window:
                # Keep a window available for each independent local request.
                new.append(window)
                break
        if new:
            windows.extend((gap.gap_id, w) for w in new)
            records[gap.gap_id] = gap.model_copy(
                update={"attempt_count": (old.attempt_count if old else 0) + 1}
            )
        elif old and old.status == "found":
            records[gap.gap_id] = old
        else:
            why = (
                "repository_search_budget"
                if result.truncated
                else (
                    "no_unread_source_window"
                    if result.matches
                    else "no_repository_match"
                )
            )
            records[gap.gap_id] = gap.model_copy(
                update={
                    "status": "exhausted" if result.truncated else "not_found",
                    "attempt_count": (old.attempt_count if old else 0) + 1,
                    "failure_reason": why,
                }
            )
    if host_navigation and windows:
        records = {
            key: gap.model_copy(update={"status": "pending", "failure_reason": None})
            if gap.gap_type in {"runtime", "external"}
            else gap
            for key, gap in records.items()
        }
    return GapPlan(tuple(records.values()), tuple(windows))


def _record(candidate_id, request, snapshot) -> ReviewEvidenceGap:
    # IDs depend on normalized task coordinates, independent of model wording or round.
    coordinates = (
        str(candidate_id),
        snapshot,
        request.gap_type,
        request.suggested_action or "",
        request.target_symbol or "",
        request.target_path or "",
        request.description
        if not (request.target_symbol or request.target_path)
        else "",
    )
    identifier = sha256("\0".join(coordinates).encode()).hexdigest()[:32]
    return ReviewEvidenceGap(
        **request.model_dump(),
        candidate_id=candidate_id,
        gap_id=identifier,
        status="pending" if request.gap_type == "repository" else "blocked",
        failure_reason=None
        if request.gap_type == "repository"
        else "material_or_analysis_required",
    )


def _requests(assessment, host_navigation) -> tuple[EvidenceGapRequest, ...]:
    # Structured requests take precedence. Older or incomplete output gets a
    # bounded fallback using only the accepted candidate's unresolved premises.
    typed = [
        EvidenceGapRequest.model_validate(row)
        for row in assessment.get("evidence_gaps", [])
    ]
    missing = list(
        dict.fromkeys(
            [
                *assessment.get("missing_premises", []),
                *(
                    p["reason"]
                    for p in assessment.get("premises", [])
                    if p["status"] == "missing"
                ),
            ]
        )
    )
    symbols = tuple(
        dict.fromkeys(symbol for text in missing for symbol in _SYMBOL.findall(text))
    )
    fallback = [
        EvidenceGapRequest(
            gap_type="repository",
            description=f"Locate {symbol}",
            target_symbol=symbol,
            suggested_action="find_symbol",
        )
        for symbol in symbols[:_MAX_REQUESTS]
    ] + [
        EvidenceGapRequest(
            gap_type="repository",
            description=f"Read {path}",
            target_path=path,
            suggested_action="read_source",
        )
        for path in missing_source_paths(assessment)[:_MAX_REQUESTS]
    ]
    runtime = [
        EvidenceGapRequest(
            gap_type="runtime",
            description=text[:500] or "Runtime evidence needed",
            suggested_action="request_material",
        )
        for text in assessment.get("runtime_unknowns", [])[:_MAX_REQUESTS]
    ]
    repository = [
        req
        for req in [*typed, *fallback]
        if req.gap_type == "repository" and (req.target_symbol or req.target_path)
    ]
    if host_navigation:
        from semflow_research.discovery.review_local_probes import local_probes

        repository = [
            *local_probes(typed, (*missing, *assessment.get("runtime_unknowns", ()))),
            *repository,
        ]
        repository = list(
            {
                (row.target_path, row.target_symbol, row.suggested_action): row
                for row in reversed(repository)
            }.values()
        )[::-1]
    repository.sort(key=lambda request: request.priority != "high")
    other = [req for req in [*typed, *runtime] if req.gap_type != "repository"]
    if not repository and not other and missing:
        other.append(
            EvidenceGapRequest(gap_type="unresolved", description=missing[0][:500])
        )
    # External dependencies do not consume the local task budget.
    return (*repository[:_MAX_REQUESTS], *other[:_MAX_REQUESTS])


def _locate(locator, gap):
    if gap.target_symbol:
        if gap.suggested_action == "find_references":
            return locator.find_references(gap.target_symbol, limit=20)
        return locator.find_symbol(gap.target_symbol, limit=20)
    return locator.find_paths(gap.target_path or "")


def _unread(evidence, filename, match_start, match_end, seen, kind):
    try:
        path = evidence.allowed(filename)
        if path.stat().st_size > 1024 * 1024:
            return None
        lines = read_source_text(path).splitlines()
    except (OSError, UnicodeError):
        return None
    except AuditError as exc:
        if exc.code in {"identity_error", "integrity_error"}:
            raise
        return None
    covered = [(w.start_line, w.end_line) for w in seen if w.file == filename]

    def unread(number):
        return all(not start <= number <= end for start, end in covered)

    if kind == "path":
        match_start, match_end = 1, len(lines)
    first, last = (
        max(1, match_start - 4),
        min(len(lines), max(match_end, match_start + 22)),
    )
    points = (n for n in range(max(first, match_start), last + 1) if unread(n))
    anchor = next(points, None)
    if anchor is None:
        return None
    first = max(first, anchor - 8)
    last = min(last, first + 39)
    while first < anchor and not all(unread(n) for n in range(first, anchor)):
        first += 1
    for number in range(anchor, last + 1):
        if not unread(number) or len("\n".join(lines[first - 1 : number])) > 3000:
            last = number - 1
            break
    if last < anchor:
        return None
    return ReviewSourceWindow(file=filename, start_line=first, end_line=last)
