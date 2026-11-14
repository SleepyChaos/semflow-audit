"""Algorithm extracted from app.services.rules.

Runtime dependencies are passed explicitly; no platform ORM or configuration.
Changes to JSON require checking the corresponding semflow_contracts/wire peer.
"""

from uuid import UUID

from semflow_contracts.modelio.stages import RuleRequest

from semflow_research.adapters.artifacts import ArtifactStore
from semflow_research.adapters.codeql.custom import (
    fixed_dependencies,
    prepare_query,
    validate_fixtures,
)
from semflow_research.adapters.retrieval.knowledge import KnowledgeRetriever
from semflow_research.adapters.retrieval.rule_routing import retrieve_rule_roles
from semflow_research.domain.errors import AuditError
from semflow_research.ports.model import ModelProvider
from semflow_research.rules.rule_drafts import confirmed_evidence
from semflow_research.rules.rule_holdouts import (
    evaluate_holdout,
    validation_fingerprint,
)
from semflow_research.state.models import Candidate, RuleVersion


class RuleService:
    def __init__(self, execution_id: str, provider: ModelProvider, *, _kernel):
        self._kernel = _kernel
        self.execution_id, self.provider = (execution_id, provider)
        self.repository = _kernel.execution_records
        self.execution = self.repository.get(execution_id)
        self.inputs = RuleRequest.model_validate(self.execution.inputs)
        self.source_context = _kernel.source_records.get(
            str(self.execution.snapshot_id)
        )
        self.directory = ArtifactStore(_kernel=_kernel).directory(execution_id)
        self.modern = self.execution.method_version in {
            "2",
            "3",
            "4",
            "5",
            "6",
            "7",
            "8",
        }
        self.experiment = (
            self.execution.policy.get("rule_experiment", {})
            if self.execution.method_version in {"3", "4", "5", "6", "7", "8"}
            else {}
        )

    def retrieve(self) -> dict:
        _kernel = self._kernel
        self.repository.active(self.execution_id)
        if self.execution.method_version in {"6", "7", "8"}:
            from semflow_research.rules.rule_materials import prepare_rule_materials

            return prepare_rule_materials(self, _kernel=_kernel)
        target = None
        if self.inputs.candidate_id:
            with _kernel.records.transaction() as session:
                row = session.get(Candidate, self.inputs.candidate_id)
                if (
                    row is None
                    or row.snapshot_id != self.source_context.id
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
                            "evidence": confirmed_evidence(
                                row, self.source_context, _kernel=_kernel
                            ),
                        }
                        if self.execution.method_version in {"3", "4", "5"}
                        else {}
                    ),
                }
        retriever = (
            retrieve_rule_roles
            if self.experiment.get("routing")
            else KnowledgeRetriever(_kernel=_kernel).retrieve
        )
        knowledge = retriever(
            _kernel.corpus_snapshot.snapshot_id,
            self.source_context.language,
            self.inputs.requirement,
            api_version=fixed_dependencies(
                self.source_context.language, _kernel=_kernel
            )[
                "codeql/"
                + (
                    "python-all"
                    if self.source_context.language == "python"
                    else "javascript-all"
                )
            ]["version"]
            if self.modern
            else None,
        )
        if self.experiment.get("framework_knowledge"):
            domain = KnowledgeRetriever(_kernel=_kernel).retrieve(
                _kernel.corpus_snapshot.snapshot_id,
                self.source_context.language,
                self.inputs.requirement,
                top_k=8,
                api_version=fixed_dependencies(
                    self.source_context.language, _kernel=_kernel
                )["codeql/python-all"]["version"],
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
            self.execution_id,
            phase="rag_retrieval",
            model=self.provider.model,
            result={"retrieval": knowledge},
        )
        return {"knowledge": knowledge, "target": target}

    def generate(self, state: dict) -> dict:
        _kernel = self._kernel
        from semflow_research.graphs.rules import build_generation_graph

        result = build_generation_graph(self, _kernel=_kernel).invoke(state)
        return {"rule_id": result["rule_id"]}

    def approve(self, state: dict) -> dict:
        _kernel = self._kernel
        from langgraph.types import interrupt

        self.repository.active(self.execution_id)
        # Peer: runtime.rule_operations.resume receives a validated human
        # ControlCommand before delivering this boolean to the saved graph.
        # AGENT: never replace this interrupt with a model assessment or a DB
        # approval flag; changed fixtures require a new action/subject digest.
        approved = interrupt(
            {
                "rule_id": state["rule_id"],
                "required": "review_positive_and_negative_fixtures",
            }
        )
        if type(approved) is not bool:
            raise AuditError("批准恢复必须是经过控制边界校验的布尔决策")
        with _kernel.records.transaction() as session:
            rule = session.get(RuleVersion, UUID(state["rule_id"]))
            rule.fixtures_approved = approved
            session.save(rule)
        return {"approved": approved}

    def validate(self, state: dict) -> dict:
        _kernel = self._kernel
        self.repository.active(self.execution_id)
        self.repository.update(self.execution_id, phase="validate_rule")
        with _kernel.records.transaction() as session:
            rule = session.get(RuleVersion, UUID(state["rule_id"]))
        pack = self.directory / "accepted-pack"
        prepare_query(pack, rule.language, rule.query, rule.modules, rule.dependencies)
        validation = validate_fixtures(
            self.directory / "validation",
            pack,
            rule.language,
            rule.fixtures,
            _kernel=_kernel,
        )
        independent = (
            evaluate_holdout(
                rule, self.directory / "independent", pack, _kernel=_kernel
            )
            if rule.purpose != "unknown"
            else {"status": "legacy_not_evaluated"}
        )
        with _kernel.records.transaction() as session:
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
                and independent.get("status") == "passed"
                and (
                    not _kernel.spec.inputs.development.project_replay
                    or (current.validation.get("project_replay") or {}).get("status")
                    in {"target_detected", "not_evaluated"}
                )
                else "draft"
            )
            final_status = current.status
            session.save(current)
            session.commit()
        self.repository.update(
            self.execution_id,
            status="completed",
            phase="rule_validation_ready"
            if final_status == "validated"
            else "rule_revision_required",
            result={
                "rule_id": str(rule.id),
                "validation": {**validation, "independent_holdout": independent},
            },
        )
        return {"validated": final_status == "validated"}
