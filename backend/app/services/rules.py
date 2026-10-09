from uuid import UUID

from sqlmodel import Session

from app.adapters.artifacts import ArtifactStore
from app.adapters.codeql.custom import (
    fixed_dependencies,
    prepare_query,
    query_digest,
    validate_fixtures,
)
from app.adapters.retrieval.knowledge import KnowledgeRetriever
from app.adapters.retrieval.rule_routing import retrieve_rule_roles
from app.contracts.stages import RuleRequest
from app.core.db import engine
from app.domain.audit import AuditError
from app.models import get_datetime_utc
from app.persistence.audit_repository import AuditRepository
from app.persistence.knowledge_models import RuleVersion
from app.persistence.stage_models import Candidate
from app.persistence.stage_repository import StageRepository
from app.ports.model import ModelProvider
from app.services.rule_drafts import confirmed_evidence
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
        self.modern = self.stage.prompt_version in {"2", "3", "4", "5", "6", "7", "8"}
        self.experiment = (
            self.stage.model_config_snapshot.get("rule_experiment", {})
            if self.stage.prompt_version in {"3", "4", "5", "6", "7", "8"}
            else {}
        )

    def retrieve(self) -> dict:
        self.repository.active(self.stage_id)
        if self.stage.prompt_version in {"6", "7", "8"}:
            from app.services.rule_materials import prepare_rule_materials

            return prepare_rule_materials(self)
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
                    **(
                        {
                            "weakness": row.weakness,
                            "location": row.location,
                            "evidence": confirmed_evidence(row, self.audit),
                        }
                        if self.stage.prompt_version in {"3", "4", "5"}
                        else {}
                    ),
                }
        retriever = (
            retrieve_rule_roles
            if self.experiment.get("routing")
            else KnowledgeRetriever().retrieve
        )
        knowledge = retriever(
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
            if self.modern
            else None,
        )
        if self.experiment.get("framework_knowledge"):
            domain = KnowledgeRetriever().retrieve(
                self.audit.owner_id,
                self.audit.language,
                self.inputs.requirement,
                top_k=8,
                api_version=fixed_dependencies(self.audit.language)[
                    "codeql/python-all"
                ]["version"],
                mode="bm25",
            )
            domain = [
                {**row, "roles": ["framework_api"]}
                for row in domain
                if row["source"].startswith("framework-api:")
            ]
            knowledge = knowledge[:4] + domain[:2]
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
        # CLI experiments use the same bounded node implementation as the job graph.
        from app.workflows.rules import build_generation_graph

        result = build_generation_graph(self).invoke(state)
        return {"rule_id": result["rule_id"]}

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
                and (
                    self.stage.prompt_version not in {"6", "7", "8"}
                    or (current.validation.get("project_replay") or {}).get("status")
                    in {"target_detected", "not_evaluated"}
                )
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
    if rule.validation.get("generation_version") in {"6", "7", "8"}:
        from app.services.rule_project_validation import check_project_validation

        check_project_validation(rule)
    rule.status, rule.published_at = "published", get_datetime_utc()
