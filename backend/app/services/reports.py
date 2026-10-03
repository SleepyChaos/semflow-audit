import json

from sqlmodel import Session, select

from app.persistence.audit_models import AuditRun
from app.persistence.knowledge_models import RuleVersion
from app.persistence.stage_models import (
    Candidate,
    Decision,
    Evidence,
    RepairRecord,
    StageRun,
)


def build_report(session: Session, audit: AuditRun) -> dict:
    stages = session.exec(
        select(StageRun)
        .where(StageRun.audit_id == audit.id)
        .order_by(StageRun.created_at)
    ).all()
    candidates = session.exec(
        select(Candidate).where(Candidate.audit_id == audit.id)
    ).all()
    ids = [row.id for row in candidates]
    decisions = (
        session.exec(
            select(Decision)
            .where(Decision.candidate_id.in_(ids))
            .order_by(Decision.created_at)
        ).all()
        if ids
        else []
    )
    evidence = session.exec(select(Evidence).where(Evidence.audit_id == audit.id)).all()
    repairs = session.exec(
        select(RepairRecord).where(RepairRecord.audit_id == audit.id)
    ).all()
    rules = session.exec(
        select(RuleVersion).where(RuleVersion.audit_id == audit.id)
    ).all()

    def dump(rows):
        return [row.model_dump(mode="json") for row in rows]

    # Re-running review must not multiply counts for the same vulnerability instance.
    by_identity = {}
    decision_times = {row.candidate_id: row.created_at for row in decisions}
    for row in candidates:
        key = row.identity_key or str(row.id)
        previous = by_identity.get(key)
        if previous is None or (
            (row.id in decision_times, decision_times.get(row.id, row.created_at))
            > (
                previous.id in decision_times,
                decision_times.get(previous.id, previous.created_at),
            )
        ):
            by_identity[key] = row
    instances = list(by_identity.values())
    counts = {
        status: sum(row.status == status for row in instances)
        for status in ["confirmed", "excluded", "pending", "insufficient"]
    }
    return {
        "schema_version": "2",
        "audit": audit.model_dump(mode="json"),
        "summary": {
            "static_alerts": len(audit.findings),
            "candidate_states": counts,
            "confirmed_ai_discoveries": sum(
                row.origin == "ai"
                and row.novelty == "new_location"
                and row.status == "confirmed"
                for row in instances
            ),
            "meaning": "AI recommendations are not counted as confirmed detection gains",
        },
        "stages": dump(stages),
        "anchor_assessments": [
            {
                "stage_id": str(stage.id),
                "assessments": stage.result.get("anchor_assessments", []),
                "unreviewed": stage.result.get("unreviewed_anchor_ids", []),
            }
            for stage in stages
            if stage.kind == "review"
        ],
        "candidates": dump(candidates),
        "decisions": dump(decisions),
        "evidence": dump(evidence),
        "repairs": dump(repairs),
        "rules": dump(rules),
        "coverage": audit.coverage,
        "limitations": [
            "未报告告警不代表安全",
            "模型判断需要真实证据与人工确认",
            "补丁验证结果不是修复正确性的完整证明",
            "样本通过不代表规则真实项目准确率",
            "未执行/失败阶段保留不确定性",
        ],
    }


def markdown_report(report: dict) -> str:
    audit = report["audit"]
    sections = [
        f"# 审计报告：{audit['project_name']}",
        f"快照：`{audit['snapshot_hash']}`\n\n语言：{audit['language']}\n\nCodeQL：{audit['codeql_version']}\n\n状态：{audit['status']}",
        "## 汇总\n\n```json\n"
        + json.dumps(report["summary"], ensure_ascii=False, indent=2)
        + "\n```",
        "## 覆盖范围\n\n```json\n"
        + json.dumps(report["coverage"], ensure_ascii=False, indent=2)
        + "\n```",
    ]
    for title, key in [
        ("原始静态告警", None),
        ("阶段执行与版本", "stages"),
        ("锚点评价与未评估范围", "anchor_assessments"),
        ("候选与人工判断", "candidates"),
        ("判断历史", "decisions"),
        ("取证证据", "evidence"),
        ("修复与验证", "repairs"),
        ("规则与知识版本", "rules"),
    ]:
        data = audit["findings"] if key is None else report[key]
        sections.append(
            f"## {title}\n\n```json\n"
            + json.dumps(data, ensure_ascii=False, indent=2)
            + "\n```"
        )
    sections.append(
        "## 解释边界\n\n" + "\n".join("- " + text for text in report["limitations"])
    )
    return "\n\n".join(sections) + "\n"
