"""Classify the next action from accepted assessment and observed source ranges."""

import json

from semflow_contracts.review_handoff import ReviewNextAction, ReviewSourceWindow

from semflow_research.adapters.review_evidence import missing_source_paths
from semflow_research.domain.errors import AuditError


def source_windows_seen(directory, batch, candidate_id):
    """Use matching accepted call payloads, including any successful feedback revision."""
    seen = []
    for attempt in [*batch.get("assessment_history", []), batch]:
        reference = attempt.get("call_reference")
        if not reference:
            continue
        path = (directory / reference / "input.json").resolve()
        if (
            not path.is_relative_to((directory / "batches").resolve())
            or not path.is_file()
        ):
            continue
        payload = json.loads(path.read_bytes())["payload"]
        if not any(
            target["candidate_id"] == candidate_id for target in payload["targets"]
        ):
            continue
        for page in payload["evidence"]:
            if page["kind"] == "code":
                ref = page["reference"]
                seen.append(
                    ReviewSourceWindow(
                        file=ref["file"],
                        start_line=ref["start_line"],
                        end_line=ref["end_line"],
                    )
                )
    return seen


def merge_windows(windows):
    merged = []
    for w in sorted(windows, key=lambda w: (w.file, w.start_line, w.end_line)):
        if (
            merged
            and merged[-1].file == w.file
            and merged[-1].end_line + 1 >= w.start_line
        ):
            prev = merged[-1]
            merged[-1] = prev.model_copy(
                update={"end_line": max(prev.end_line, w.end_line)}
            )
        else:
            merged.append(w)
    return tuple(merged)


def next_action(state, assessment, seen, evidence):
    if state == "assessed":
        return ReviewNextAction(kind="none")
    if state == "unreviewed":
        return ReviewNextAction(kind="retry_execution")
    windows = []
    for file in missing_source_paths(assessment):
        if len(windows) >= 3:
            break
        window = _unread_window(evidence, file, seen)
        if window is not None:
            windows.append(window)
    if windows:
        return ReviewNextAction(kind="gather_source", source_windows=tuple(windows))
    missing_policy = any(
        row["premise"] == "input_or_policy"
        and row["status"] == "missing"
        and row.get("policy_basis") == "unknown"
        for row in assessment.get("premises", ())
    )
    policy_property = assessment.get("security_property") in {
        "authentication",
        "authorization",
        "object_ownership",
        "rate_limiting",
        "security_logging",
    }
    if (missing_policy and policy_property) or assessment.get("runtime_unknowns"):
        return ReviewNextAction(kind="collect_material")
    return ReviewNextAction(kind="manual_triage")


def _unread_window(evidence, file, seen):
    try:
        path = evidence.allowed(file)
        if not path.is_file() or path.stat().st_size > 1024 * 1024:
            return None
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return None
    except AuditError as error:
        if error.code in {"identity_error", "integrity_error"}:
            raise
        return None
    start = 1
    end = len(lines)
    for w in seen:
        if w.file != file or w.end_line < start:
            continue
        if w.start_line > start:
            end = w.start_line - 1
            break
        start = w.end_line + 1
    end = min(end, start + 39)
    while start <= end and len("\n".join(lines[start - 1 : end])) > 3000:
        end -= 1
    if start <= end:
        return ReviewSourceWindow(file=file, start_line=start, end_line=end)
    return None
