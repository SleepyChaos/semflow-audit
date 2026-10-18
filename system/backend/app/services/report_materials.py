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


def review_context(source, group):
    ids = {row["id"] for row in group}
    stages = {
        row.get("review", {}).get("stage_id") for row in group if row.get("review")
    }
    contexts = source.get("review_context", [])
    selected = [row for row in contexts if row.get("stage_id") in stages]
    if contexts and contexts[-1] not in selected:
        selected.append(contexts[-1])
    return [
        {
            **row,
            "root_relations": [
                relation
                for relation in row.get("root_relations", [])
                if ids.intersection(relation.get("candidate_ids", []))
            ],
        }
        for row in selected
    ]


def candidate_material(row, assessment_ids):
    # The full review is already present in assessments. Keep one copy of its
    # narrative, premises and exploitation instead of sending it twice per issue.
    row = {
        key: value
        for key, value in row.items()
        if key
        in {
            "id",
            "origin",
            "title",
            "description",
            "status",
            "weakness",
            "location",
            "review",
            "classification",
            "evidence_ids",
            "issue",
        }
    }
    if row.get("issue"):
        row["issue"] = {
            **{key: value for key, value in row["issue"].items() if key != "sources"},
            "sources": [
                {
                    "id": source["id"],
                    "origin": source["origin"],
                    "classification": source["classification"],
                    "review": {
                        key: value
                        for key, value in (source.get("review") or {}).items()
                        if key
                        in {
                            "status",
                            "reason",
                            "checked_premises",
                            "missing_premises",
                            "runtime_unknowns",
                            "evidence_ids",
                        }
                    },
                }
                for source in row["issue"]["sources"]
            ],
        }
    if row["id"] not in assessment_ids or not row.get("review"):
        return row
    return {
        **row,
        "review": {
            key: value
            for key, value in row["review"].items()
            if key in {"stage_id", "stage_status", "status", "evaluated", "updated_at"}
        },
    }


def evidence_material(row):
    # Reports summarize validated reviews, rather than repeating whole source
    # windows in each batch. The frozen source and exported report retain them.
    return {
        key: excerpt(value, 600) if key == "content" else value
        for key, value in row.items()
        if key in {"id", "kind", "reference", "snapshot_hash", "digest", "content"}
    }


def report_batches(source):
    candidates = source["candidates"]
    groups = [candidates[i : i + 4] for i in range(0, len(candidates), 4)] or [[]]
    result = []
    for group in groups:
        ids = {row["id"] for row in group}
        evidence_ids = {item for row in group for item in row.get("evidence_ids", [])}
        assessments = latest_per_candidate(source.get("assessments", []), ids)
        assessment_ids = {row["candidate_id"] for row in assessments}
        payload = {
            "audit": {
                key: value
                for key, value in source["audit"].items()
                if key != "findings"
            },
            "summary": source["summary"],
            "candidates": [candidate_material(row, assessment_ids) for row in group],
            "required_candidate_ids": [row["id"] for row in group],
            "issue_evidence_binding": {
                row["id"]: row.get("evidence_ids", []) for row in group
            },
            "evidence": [
                evidence_material(row)
                for row in source["evidence"]
                if row["id"] in evidence_ids
            ],
            "decisions": latest_per_candidate(source["decisions"], ids),
            "assessments": assessments,
            "review_context": review_context(source, group),
            "material_scope": "只撰写当前候选详情；全局覆盖、修复、验证和规则在独立全局报告中汇总，本批未提供不等于不存在。长文本可节选，所有候选都会纳入最终报告。",
        }
        for limit in (4000, 1600, 600):
            bounded = excerpt(payload, limit)
            if len(json.dumps(bounded, ensure_ascii=False).encode()) <= 34000:
                break
        if (
            len(json.dumps(bounded, ensure_ascii=False).encode()) > 34000
            and len(group) > 1
        ):
            # Split proportionally so a large group does not become N repeated
            # one-issue requests, each carrying project-level context again.
            middle = len(group) // 2
            for subgroup in [group[:middle], group[middle:]]:
                result.extend(report_batches({**source, "candidates": subgroup}))
        else:
            result.append(bounded)
    for index, payload in enumerate(result):
        payload["batch"] = {"scope": "issues", "index": index + 1, "total": len(result)}
    return result


def combine_reports(reports, overview):
    return {
        "overview": overview.overview,
        "issues": [
            issue.model_dump(mode="json") for row in reports for issue in row.issues
        ],
        "repair_review": overview.repair_review,
        "limitations": list(
            dict.fromkeys(
                [
                    *overview.limitations,
                    *(item for row in reports for item in row.limitations),
                ]
            )
        ),
        "next_steps": overview.next_steps,
    }
