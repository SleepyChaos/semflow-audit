import json
from uuid import UUID

from sqlmodel import Session

from app.adapters.artifacts import ArtifactStore
from app.adapters.codeql.custom import prepare_query, query_digest, run_query
from app.core.db import engine
from app.domain.audit import AuditError
from app.persistence.knowledge_models import RuleVersion
from app.services.rule_holdouts import check_modern_validation


def owned_published_rule(
    identifier: UUID, owner_id: UUID, language: str, allow_retired: bool = False
) -> RuleVersion:
    with Session(engine) as session:
        rule = session.get(RuleVersion, identifier)
        if (
            rule is None
            or rule.owner_id != owner_id
            or rule.language != language
            or rule.status
            not in ({"published", "retired"} if allow_retired else {"published"})
        ):
            raise AuditError("规则版本不存在、未发布或语言不匹配")
        if query_digest(rule.query, rule.modules) != rule.query_hash:
            raise AuditError("已发布规则版本完整性检查失败")
        check_modern_validation(rule)
        if rule.validation.get("generation_version") in {"6", "7", "8"}:
            from app.services.rule_project_validation import check_project_validation

            check_project_validation(rule)
        session.expunge(rule)
        return rule


def execute_evidence_query(evidence, rule_id: str) -> dict:
    rule = owned_published_rule(
        UUID(rule_id), evidence.audit.owner_id, evidence.audit.language
    )
    directory = (
        ArtifactStore().directory(str(evidence.stage_id))
        / "evidence-queries"
        / str(rule.id)
    )
    directory.mkdir(parents=True, exist_ok=True)
    pack = directory / "pack"
    prepare_query(pack, rule.language, rule.query, rule.modules, rule.dependencies)
    database = ArtifactStore().directory(str(evidence.audit.id)) / "database"
    findings = run_query(
        database,
        pack,
        directory / "results.sarif",
        directory / "execution.log",
        evidence.audit.snapshot_hash,
    )
    filtered = []
    for finding in findings:
        try:
            for location in finding["locations"]:
                evidence.allowed(location["file"])
            scoped_flows = []
            for flow in finding.get("code_flows", []):
                scoped = []
                for location in flow:
                    try:
                        evidence.allowed(location["file"])
                        scoped.append(location)
                    except AuditError:
                        continue
                if scoped:
                    scoped_flows.append(scoped)
            finding["code_flows"] = scoped_flows
            filtered.append(finding)
        except AuditError:
            continue
    return evidence.record(
        "query",
        json.dumps(filtered, ensure_ascii=False),
        {
            "rule_version": str(rule.id),
            "query_hash": rule.query_hash,
            "filtered_to_scope": True,
            "query_evaluated_database": str(evidence.audit.id),
        },
    )
