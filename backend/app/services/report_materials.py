"""Model-facing redaction and bounded batches; private audit history stays intact."""

import json
import re

SECRET_KEY = re.compile(
    r"(?:password|passwd|api[_-]?key|access[_-]?token|refresh[_-]?token|secret[_-]?key|authorization|client[_-]?secret|private[_-]?key)$",
    re.I,
)
SECRET_TEXT = [
    re.compile(r"(?i)(\b(?:Bearer|Basic)\s+)[A-Za-z0-9._~+/=-]+"),
    re.compile(
        r"(?i)(\b(?:password|passwd|api[_-]?key|access[_-]?token|refresh[_-]?token|secret[_-]?key|client[_-]?secret)(?:['\"]\s*\])?['\"]?\s*[=:]\s*['\"]?)[^\s'\";,}]+"
    ),
    re.compile(r"\b(?:sk-|ghp_|github_pat_)[A-Za-z0-9_-]{12,}"),
    re.compile(
        r"(?s)-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----"
    ),
    re.compile(r"(?i)([a-z][a-z0-9+.-]*://[^\s/:@]+:)[^\s/@]+(?=@)"),
]


def redact(value):
    if isinstance(value, dict):
        return {
            key: "[凭据已隐藏]" if SECRET_KEY.search(key) else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str):
        for pattern in SECRET_TEXT:
            value = pattern.sub(
                lambda match: (match[1] if match.lastindex else "") + "[凭据已隐藏]",
                value,
            )
    return value


def excerpt(value, limit):
    if isinstance(value, str) and len(value) > limit:
        return (
            value[:limit]
            + "\n[材料已节选；未展示部分不能作为已核实事实，完整记录保留在原始报告中]"
        )
    if isinstance(value, dict):
        return {key: excerpt(item, limit) for key, item in value.items()}
    if isinstance(value, list):
        return [excerpt(item, limit) for item in value]
    return value


def latest_per_candidate(rows, ids):
    latest = {}
    for row in rows:
        if row.get("candidate_id") in ids:
            latest[row["candidate_id"]] = row
    return list(latest.values())


def coverage_summary(coverage):
    # Keep real engine/inspection states while excluding potentially huge matrices.
    if not isinstance(coverage, dict):
        return coverage
    return {
        key: coverage_summary(value) if isinstance(value, dict) else value
        for key, value in coverage.items()
        if key not in {"matrix", "files", "deferred_windows", "skipped"}
        and not isinstance(value, list)
    }


def report_batches(source):
    candidates = source["candidates"]
    groups = [candidates[i : i + 8] for i in range(0, len(candidates), 8)] or [[]]
    result = []
    for group in groups:
        ids = {row["id"] for row in group}
        evidence_ids = {item for row in group for item in row.get("evidence_ids", [])}
        payload = {
            "audit": {
                key: value
                for key, value in source["audit"].items()
                if key != "findings"
            },
            "summary": source["summary"],
            "coverage": coverage_summary(source["coverage"]),
            "candidates": group,
            "issue_evidence_binding": {
                row["id"]: row.get("evidence_ids", []) for row in group
            },
            "evidence": [
                row for row in source["evidence"] if row["id"] in evidence_ids
            ],
            "decisions": latest_per_candidate(source["decisions"], ids),
            "assessments": latest_per_candidate(source.get("assessments", []), ids),
            "repairs": source["repairs"][-12:],
            "verification": source.get("verification", []),
            "rules": source["rules"][-12:],
            "stages": source["stages"][-20:],
            "material_scope": "当前候选分批生成；历史记录和长文本可节选，不能将节选视作完整源码或完整验证。所有候选都会纳入最终报告。",
        }
        for limit in (12000, 4000, 1600, 600):
            bounded = excerpt(payload, limit)
            if len(json.dumps(bounded, ensure_ascii=False).encode()) <= 45000:
                break
        if (
            len(json.dumps(bounded, ensure_ascii=False).encode()) > 45000
            and len(group) > 1
        ):
            # Split further when one eight-candidate batch has extensive evidence.
            for row in group:
                result.extend(report_batches({**source, "candidates": [row]}))
        else:
            result.append(bounded)
    for index, payload in enumerate(result):
        payload["batch"] = {"index": index + 1, "total": len(result)}
    return result


def combine_reports(reports):
    return {
        "overview": "\n\n".join(row.overview for row in reports),
        "issues": [
            issue.model_dump(mode="json") for row in reports for issue in row.issues
        ],
        "repair_review": "\n\n".join(
            dict.fromkeys(row.repair_review for row in reports)
        ),
        "limitations": list(
            dict.fromkeys(item for row in reports for item in row.limitations)
        ),
        "next_steps": list(
            dict.fromkeys(item for row in reports for item in row.next_steps)
        ),
    }
