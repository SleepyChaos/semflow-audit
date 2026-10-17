"""Initialize reusable local rules; real CodeQL checks precede publication.

Run with the backend runtime/configuration, e.g. PYTHONPATH=backend python
scripts/seed_baseline_rules.py. This does not call a model or upload source.
"""

import argparse
import json
from types import SimpleNamespace

from app.adapters.artifacts import ArtifactStore
from app.adapters.codeql.baseline_rules import CATALOG, baseline_definition
from app.adapters.codeql.custom import fixed_dependencies, query_digest
from app.core.db import engine
from app.domain.audit import AuditError
from app.persistence.audit_models import AuditRun
from app.persistence.knowledge_models import RuleVersion
from app.persistence.stage_models import StageRun
from app.persistence.workspace import resolve_workspace
from app.services.rules import RuleService, publish_rule
from sqlmodel import Session, select


def seed(identifier, publish=False):
    definition = baseline_definition(identifier)
    with Session(engine) as db:
        workspace = resolve_workspace(db)
        existing = db.exec(
            select(RuleVersion).where(
                RuleVersion.owner_id == workspace.id,
                RuleVersion.title == definition["title"],
                RuleVersion.query_hash == query_digest(definition["query"], {}),
                RuleVersion.status.in_(["validated", "published"]),
            )
        ).first()
        if existing:
            if publish and existing.status == "validated":
                publish_rule(existing)
                db.add(existing)
                db.commit()
            return {
                "id": str(existing.id),
                "title": existing.title,
                "status": existing.status,
                "existing": True,
            }
        audit = db.exec(
            select(AuditRun)
            .where(
                AuditRun.owner_id == workspace.id,
                AuditRun.language == definition["language"],
                AuditRun.status == "completed",
            )
            .order_by(AuditRun.created_at.desc())
        ).first()
        if audit is None:
            raise AuditError(
                f"{definition['language']} 需要至少一个已完成的本地审计作为规则归属"
            )
        stage = StageRun(
            audit_id=audit.id,
            kind="rule",
            status="running",
            phase="validate_rule",
            prompt_version="baseline-1",
            model="installed-codeql-query-pack",
            inputs={
                "purpose": "vulnerability_detector",
                "holdout_id": definition["holdout_id"],
                "requirement": definition["title"]
                + "；复用固定版本官方查询，不声称新增覆盖缺口。",
                "source_paths": [],
                "strategy": "extend",
                "candidate_id": None,
            },
            model_config_snapshot={
                "origin": "installed-codeql-baseline",
                "source": definition["source"],
            },
        )
        db.add(stage)
        db.commit()
        rule = RuleVersion(
            owner_id=workspace.id,
            audit_id=audit.id,
            stage_id=stage.id,
            language=definition["language"],
            title=definition["title"],
            purpose="vulnerability_detector",
            holdout_id=definition["holdout_id"],
            strategy="extend",
            query=definition["query"],
            modules={},
            query_hash=query_digest(definition["query"], {}),
            dependencies=fixed_dependencies(definition["language"]),
            fixtures=definition["fixtures"],
            fixtures_approved=True,
            fixture_approval_reason="按用户初始化规则库的请求，核对维护的正样例危险输入及反样例安全处理；真实 CodeQL 验收通过后才发布。",
            validation={
                "origin": "installed-codeql-baseline",
                "source": definition["source"],
                "generation_version": "baseline-1",
                "coverage_analysis": "复用已安装的官方规则；作为可选基础版本，不宣称发现基线之外的新漏洞或完成原项目修复。",
            },
        )
        db.add(rule)
        db.commit()
        stage_id, rule_id = str(stage.id), str(rule.id)
        print(
            json.dumps(
                {"starting": identifier, "rule_id": rule_id, "stage_id": stage_id}
            ),
            flush=True,
        )
    directory = ArtifactStore().directory(stage_id)
    (directory / "baseline-source.json").write_text(json.dumps(definition["source"]))
    try:
        RuleService(
            stage_id, SimpleNamespace(model="installed-codeql-query-pack")
        ).validate({"rule_id": rule_id})
        with Session(engine) as db:
            from uuid import UUID

            rule = db.get(RuleVersion, UUID(rule_id))
            if rule.status != "validated":
                raise AuditError("基础规则未通过完整验收，保留草稿和真实检查结果")
            if publish:
                publish_rule(rule)
                db.add(rule)
                db.commit()
            return {
                "id": str(rule.id),
                "title": rule.title,
                "status": rule.status,
                "fixtures": rule.validation["status"],
                "independent": rule.validation["independent_holdout"]["status"],
            }
    except Exception as exc:
        from app.persistence.stage_repository import StageRepository

        StageRepository().update(stage_id, status="failed", error=str(exc)[:1000])
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--rules", nargs="+", choices=list(CATALOG), default=list(CATALOG)
    )
    parser.add_argument("--publish", action="store_true", help="验收通过后发布基础版本")
    args = parser.parse_args()
    for identifier in args.rules:
        print(
            json.dumps(seed(identifier, args.publish), ensure_ascii=False), flush=True
        )


if __name__ == "__main__":
    main()
