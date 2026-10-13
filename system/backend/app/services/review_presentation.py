"""Narratives cannot claim deployed exploitation or cite unrelated/unread source."""

from app.domain.audit import AuditError


def validate_detail(assessment, evidence, require_chinese=False):
    detail = assessment.detail
    example = detail.exploitation
    if require_chinese:
        import re

        texts = [
            assessment.reason,
            detail.title,
            detail.description,
            detail.impact,
            example.expected_result,
            *assessment.checked_premises,
            *assessment.missing_premises,
            *assessment.runtime_unknowns,
            *example.prerequisites,
            *example.steps,
        ]
        if any(
            text.strip() and not re.search(r"[\u4e00-\u9fff]", text) for text in texts
        ):
            raise AuditError("面向用户的漏洞说明必须用中文，保留标识符与源码引用即可")
    cited = list(dict.fromkeys([*detail.evidence_ids, *example.evidence_ids]))
    evidence(cited)
    rows = evidence(example.evidence_ids)
    if example.status == "illustrative":
        if assessment.assessment != "supported":
            raise AuditError("未支持的漏洞不能提供声称可利用的用例")
        if not example.entrypoint or not example.steps or not example.example:
            raise AuditError("项目利用用例需要入口、步骤及具体示例")
        quote = example.source_quote.strip()
        if len(quote) < 3 or not any(
            row["kind"] == "code" and quote in row["content"] for row in rows
        ):
            raise AuditError("利用用例必须引用已读取项目源码中的实际入口或操作")
    if example.status == "blocked" and assessment.assessment != "excluded":
        raise AuditError("阻断用例仅用于已由反证排除的候选")
    if assessment.assessment == "excluded" and example.status != "blocked":
        raise AuditError("误报应展示实际阻断依据，而非可成功利用的用例")
    combined = list(dict.fromkeys([*assessment.evidence_ids, *cited]))
    if len(combined) > 30:
        raise AuditError("候选证据过多，请聚焦本漏洞的实际证明路径")
    assessment.evidence_ids = combined
