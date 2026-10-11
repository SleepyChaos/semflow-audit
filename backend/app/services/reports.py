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
from app.services.readable_reports import markdown_report as markdown_report
from app.services.result_explanations import explain_candidate, explain_validation


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
    report = {
        "schema_version": "2",
        "reader_guide": {
            "candidates": [
                explain_candidate(row.model_dump(mode="json"), dump(evidence))
                for row in instances
            ],
            "repairs": [
                {"repair_id": str(row.id), "checks": explain_validation(row.validation)}
                for row in repairs
            ],
        },
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
        "discovery": [
            {"stage_id": str(stage.id), "status": stage.status, "result": stage.result}
            for stage in stages
            if stage.kind == "scout"
        ],
        "root_relations": [
            {
                "stage_id": str(stage.id),
                "relations": stage.result.get("root_relations", []),
                "meaning": "Proposals only; original candidates and counts retained",
            }
            for stage in stages
            if stage.kind == "review"
            and stage.prompt_version in {"4", "5", "6", "7", "8", "9", "10"}
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
    from app.services.report_generation import report_state, source_fingerprint

    report["ai_report"] = report_state(stages, source_fingerprint(report))
    return report
