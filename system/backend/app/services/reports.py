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
        select(Candidate)
        .where(Candidate.audit_id == audit.id)
        .order_by(Candidate.created_at)
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

    from app.services.candidate_views import present_candidates

    instances = present_candidates(
        candidates, stages, decisions, audit, grouped=True, evidence=dump(evidence)
    )
    counts = {
        status: sum(row["status"] == status for row in instances)
        for status in ["confirmed", "excluded", "pending", "insufficient"]
    }
    from app.services.repair_comparison import comparison_state

    verification = [
        {"repair_id": str(row.id), "comparison": comparison_state(session, row)}
        for row in repairs
    ]
    report = {
        "schema_version": "2",
        "reader_guide": {
            "candidates": [explain_candidate(row, dump(evidence)) for row in instances],
            "repairs": [
                {
                    "repair_id": str(row.id),
                    "checks": explain_validation(
                        row.validation,
                        next(
                            item["comparison"]
                            for item in verification
                            if item["repair_id"] == str(row.id)
                        ),
                    ),
                }
                for row in repairs
            ],
        },
        "audit": audit.model_dump(mode="json"),
        "summary": {
            "static_alerts": len(audit.findings),
            "candidate_states": counts,
            "confirmed_ai_discoveries": sum(
                row["origin"] == "ai"
                and "static" not in row["issue"]["origins"]
                and row["novelty"] == "new_location"
                and row["status"] == "confirmed"
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
                "meaning": "Original proposals and source candidates retained; displayed issues use evidence-backed grouping",
            }
            for stage in stages
            if stage.kind == "review"
            and stage.prompt_version in {"4", "5", "6", "7", "8", "9", "10", "11", "12"}
        ],
        "candidates": instances,
        "candidate_history": present_candidates(candidates, stages, decisions, audit),
        "decisions": dump(decisions),
        "evidence": dump(evidence),
        "repairs": dump(repairs),
        "rules": dump(rules),
        "verification": verification,
        "coverage": audit.coverage,
        "limitations": [
            "未报告告警不代表安全",
            "AI 复核基于真实证据，人工可调整分类",
            "补丁验证结果不是修复正确性的完整证明",
            "样本通过不代表规则真实项目准确率",
            "未执行/失败阶段保留不确定性",
        ],
    }
    from app.services.report_generation import report_state, source_fingerprint

    report["ai_report"] = report_state(stages, source_fingerprint(report))
    return report
