from uuid import UUID

from sqlmodel import Session

from app.adapters.artifacts import ArtifactStore
from app.adapters.codeql.custom import (
    compile_query,
    fixed_dependencies,
    prepare_query,
    query_digest,
    validate_fixtures,
    write_fixtures,
)
from app.adapters.retrieval.knowledge import KnowledgeRetriever
from app.contracts.stages import RuleRequest, RuleResponse
from app.core.db import engine
from app.domain.audit import AuditError
from app.models import get_datetime_utc
from app.persistence.audit_repository import AuditRepository
from app.persistence.knowledge_models import RuleVersion
from app.persistence.stage_models import Candidate
from app.persistence.stage_repository import StageRepository
from app.ports.model import ModelProvider
from app.services.rule_holdouts import (
    check_modern_validation,
    evaluate_holdout,
    validation_fingerprint,
)


class RuleService:
    def __init__(self, stage_id: str, provider: ModelProvider):
        self.stage_id, self.provider = stage_id, provider
        self.repository = StageRepository()
        self.stage = self.repository.get(stage_id)
        self.inputs = RuleRequest.model_validate(self.stage.inputs)
        self.audit = AuditRepository().get(str(self.stage.audit_id))
        self.directory = ArtifactStore().directory(stage_id)

    def retrieve(self) -> dict:
        self.repository.active(self.stage_id)
        target = None
        if self.inputs.candidate_id:
            with Session(engine) as session:
                row = session.get(Candidate, self.inputs.candidate_id)
                if (
                    row is None
                    or row.audit_id != self.audit.id
                    or row.status != "confirmed"
                ):
                    raise AuditError("规则提炼只能选择本次审计的已确认缺陷")
                target = {
                    "title": row.title,
                    "description": row.description,
                    "evidence_ids": row.evidence_ids,
                }
        knowledge = KnowledgeRetriever().retrieve(
            self.audit.owner_id,
            self.audit.language,
            self.inputs.requirement,
            api_version=fixed_dependencies(self.audit.language)[
                "codeql/"
                + (
                    "python-all"
                    if self.audit.language == "python"
                    else "javascript-all"
                )
            ]["version"]
            if self.stage.prompt_version == "2"
            else None,
        )
        if not knowledge:
            raise AuditError("知识库没有相关检索证据；请导入语言/API/规则知识后再生成")
        self.repository.update(
            self.stage_id,
            phase="rag_retrieval",
            model=self.provider.model,
            result={"retrieval": knowledge},
        )
        return {"knowledge": knowledge, "target": target}

    def generate(self, state: dict) -> dict:
        self.repository.active(self.stage_id)
        dependencies = fixed_dependencies(self.audit.language)
        context = {
            "requirement": self.inputs.requirement,
            "strategy": self.inputs.strategy,
            "purpose": self.inputs.purpose,
            "language": self.audit.language,
            "knowledge": state["knowledge"],
            "confirmed_target": state["target"],
            "existing_coverage": {
                "baseline": self.audit.query_pack,
                "alerts": self.audit.findings,
                "published_versions": self.audit.custom_rule_ids,
            },
            "dependencies": dependencies,
        }
        last_error = None
        response = None
        # A bounded compiler feedback loop, before any human fixture approval.
        for attempt in range(2):
            context["compiler_feedback"] = last_error
            response = self.provider.generate("rule", context, RuleResponse)
            self.repository.update(
                self.stage_id, usage=self.provider.usage, phase="compile_draft"
            )
            if not set(map(str, response.knowledge_ids)).issubset(
                {row["id"] for row in state["knowledge"]}
            ):
                raise AuditError("模型引用了未检索到的知识片段")
            if (
                self.inputs.strategy != "auto"
                and response.strategy != self.inputs.strategy
            ):
                raise AuditError("生成策略与用户选择不一致")
            if (
                self.stage.prompt_version == "2"
                and response.purpose != self.inputs.purpose
            ):
                raise AuditError("规则用途与需求不一致")
            if (
                response.strategy == "model"
                or (
                    self.stage.prompt_version == "2"
                    and self.inputs.purpose == "framework_model"
                )
            ) and not response.modules:
                raise AuditError("模型补充策略必须包含 .qll 建模模块")
            pack = self.directory / f"draft-{attempt}"
            try:
                prepare_query(
                    pack,
                    self.audit.language,
                    response.query,
                    response.modules,
                    dependencies,
                )
                fixtures = {
                    "positive": response.positive.model_dump(),
                    "negative": response.negative.model_dump(),
                }
                write_fixtures(
                    self.directory / f"fixture-check-{attempt}" / "positive",
                    self.audit.language,
                    fixtures["positive"],
                )
                write_fixtures(
                    self.directory / f"fixture-check-{attempt}" / "negative",
                    self.audit.language,
                    fixtures["negative"],
                )
                if (
                    not fixtures["positive"]["expected"]
                    or fixtures["negative"]["expected"]
                ):
                    raise AuditError("生成样本必须具有正例预期和空反例预期")
                compile_query(pack, self.directory / "execution.log")
                last_error = None
                break
            except AuditError as exc:
                last_error = (
                    str(exc) + "\n" + ArtifactStore().log_tail(self.stage_id)[-5000:]
                )
        if last_error:
            raise AuditError("两次规则编译/契约验证均未通过；草稿与日志已保留")
        with Session(engine) as session:
            rule = RuleVersion(
                owner_id=self.audit.owner_id,
                audit_id=self.audit.id,
                stage_id=self.stage.id,
                language=self.audit.language,
                purpose=self.inputs.purpose
                if self.stage.prompt_version == "2"
                else "unknown",
                holdout_id=self.inputs.holdout_id,
                title=response.title,
                strategy=response.strategy,
                query=response.query,
                modules=response.modules,
                query_hash=query_digest(response.query, response.modules),
                dependencies=dependencies,
                fixtures=fixtures,
                retrieval=[
                    row
                    for row in state["knowledge"]
                    if row["id"] in set(map(str, response.knowledge_ids))
                ],
                validation={
                    "compile": "passed",
                    "coverage_analysis": response.coverage_analysis,
                    "attempts": attempt + 1,
                },
            )
            session.add(rule)
            session.commit()
            session.refresh(rule)
        self.repository.update(
            self.stage_id,
            phase="awaiting_fixture_approval",
            result={
                "rule_id": str(rule.id),
                "coverage_analysis": response.coverage_analysis,
                "retrieval": rule.retrieval,
            },
        )
        return {"rule_id": str(rule.id)}

    def approve(self, state: dict) -> dict:
        from langgraph.types import interrupt

        self.repository.active(self.stage_id)
        with Session(engine) as session:
            rule = session.get(RuleVersion, UUID(state["rule_id"]))
            approved = rule.fixtures_approved
        if not approved:
            interrupt(
                {
                    "rule_id": state["rule_id"],
                    "required": "review_positive_and_negative_fixtures",
                }
            )
        with Session(engine) as session:
            rule = session.get(RuleVersion, UUID(state["rule_id"]))
            if not rule.fixtures_approved:
                raise AuditError("规则样本尚未人工批准")
        return {"approved": True}

    def validate(self, state: dict) -> dict:
        self.repository.active(self.stage_id)
        self.repository.update(self.stage_id, phase="validate_rule")
        with Session(engine) as session:
            rule = session.get(RuleVersion, UUID(state["rule_id"]))
            session.expunge(rule)
        pack = self.directory / "accepted-pack"
        prepare_query(pack, rule.language, rule.query, rule.modules, rule.dependencies)
        validation = validate_fixtures(
            self.directory / "validation", pack, rule.language, rule.fixtures
        )
        independent = (
            evaluate_holdout(rule, self.directory / "independent", pack)
            if rule.purpose != "unknown"
            else {"status": "legacy_not_evaluated"}
        )
        with Session(engine) as session:
            current = session.get(RuleVersion, rule.id)
            current.validation = {
                **current.validation,
                **validation,
                "query_hash": current.query_hash,
                "validation_fingerprint": validation_fingerprint(rule),
                "independent_holdout": independent,
            }
            current.status = (
                "validated"
                if validation["status"] == "passed"
                and (rule.purpose == "unknown" or independent.get("status") == "passed")
                else "draft"
            )
            final_status = current.status
            session.add(current)
            session.commit()
        self.repository.update(
            self.stage_id,
            status="completed",
            phase="awaiting_rule_publication"
            if final_status == "validated"
            else "rule_revision_required",
            result={
                "rule_id": str(rule.id),
                "validation": {**validation, "independent_holdout": independent},
            },
        )
        return {"validated": final_status == "validated"}


def publish_rule(rule: RuleVersion) -> None:
    if (
        not rule.fixtures_approved
        or rule.validation.get("status") != "passed"
        or rule.status != "validated"
    ):
        raise AuditError("规则发布需要人工样本批准及正反例完整验收")
    if rule.validation.get("query_hash") != query_digest(rule.query, rule.modules):
        raise AuditError("规则内容已变化，必须重新验收")
    check_modern_validation(rule)
    rule.status, rule.published_at = "published", get_datetime_utc()
