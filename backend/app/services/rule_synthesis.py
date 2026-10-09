"""Bounded rule synthesis steps; graph state contains artifact references, not QL."""

import hashlib
import json

from sqlmodel import Session, select

from app.adapters.codeql.custom import (
    compile_query,
    fixed_dependencies,
    prepare_query,
    query_digest,
    validate_fixtures,
    write_fixtures,
)
from app.adapters.codeql.flask_spec import generate_flask_spec
from app.adapters.codeql.model_spec import generate_framework_spec
from app.adapters.codeql.rule_spec import generate_from_spec
from app.adapters.codeql.type_probe import probe_types
from app.contracts.stages import RuleResponse, RuleResponseV6
from app.core.db import engine
from app.domain.audit import AuditError
from app.persistence.knowledge_models import RuleVersion
from app.persistence.stage_repository import StageCancelled
from app.services.rule_drafts import save_candidate, save_diagnostic


class RuleSynthesis:
    def __init__(self, service):
        self.service = service

    def _pack(self, state):
        return self.service.directory / f"draft-{state['attempt'] - 1}"

    def _load(self, state):
        pack = self._pack(state)
        if state.get("candidate_digest"):
            self._verify_candidate(pack, state["candidate_digest"])
        return RuleResponse.model_validate_json((pack / "candidate.json").read_text())

    @staticmethod
    def _verify_candidate(pack, digest):
        content = (pack / "candidate.json").read_bytes()
        if hashlib.sha256(content).hexdigest() != digest:
            raise AuditError("已生成规则候选被修改，不能继续验证或持久化")

    def _phase(self, name):
        s = self.service
        s.repository.active(s.stage_id)
        s.repository.update(s.stage_id, phase=name, usage=s.provider.usage)

    def _context(self, state):
        from app.services.rule_context import build_rule_context

        return build_rule_context(self, state)

    def _knowledge(self, state):
        if self.service.stage.prompt_version in {"6", "7", "8"}:
            from app.services.rule_materials import load_rule_materials

            return load_rule_materials(self.service, state)["knowledge"]
        return state["knowledge"]

    def propose(self, state):
        self._phase("generate_rule")
        s = self.service
        attempt = state.get("attempt", 0) + 1
        if attempt > 2:
            raise AuditError("规则候选尝试预算已耗尽")
        context = self._context(state)
        pack = s.directory / f"draft-{attempt - 1}"
        pack.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps(context, ensure_ascii=False, indent=2)
        if s.stage.prompt_version in {"6", "7", "8"}:
            from app.services.context_materials import semantic_policy

            model_chars = (
                len(
                    json.dumps(
                        {"untrusted_analysis_material": context}, ensure_ascii=False
                    )
                )
                if s.stage.prompt_version == "8"
                else len(serialized)
            )
            if model_chars > semantic_policy(s.directory)["context_chars"]:
                raise AuditError(
                    "规则输入超过上下文预算；请缩小目标或参考材料",
                    code="context_budget",
                )
        input_digest = hashlib.sha256(serialized.encode()).hexdigest()
        receipt = pack / "generation-receipt.json"
        if receipt.exists():
            saved = json.loads(receipt.read_text())
            if saved["input_digest"] != input_digest:
                raise AuditError("恢复生成时输入与已保存的候选不一致")
            self._verify_candidate(pack, saved["candidate_digest"])
            return {
                "attempt": attempt,
                "draft_ok": False,
                "draft_path": str(pack.relative_to(s.directory)),
                "candidate_digest": saved["candidate_digest"],
            }
        if (pack / "input.json").exists():
            raise AuditError("上次候选生成未完整提交；保留产物，请创建新的规则阶段")
        (pack / "input.json").write_text(serialized)
        provenance = None
        from app.adapters.codeql.grounded_spec import (
            can_constrain,
            generate_grounded_spec,
        )

        if (
            s.stage.prompt_version in {"7", "8"}
            and s.experiment.get("generation_constraint", True)
            and can_constrain(context, strict_scope=s.stage.prompt_version == "8")
        ):
            response, provenance = generate_grounded_spec(s.provider, context)
        elif s.experiment.get("flask_route_spec"):
            response, provenance = generate_flask_spec(s.provider, context)
        elif s.experiment.get("framework_spec"):
            response, provenance = generate_framework_spec(
                s.provider, context, s.directory / f"spec-{attempt - 1}.json"
            )
        elif s.experiment.get("spec"):
            response, provenance = generate_from_spec(s.provider, context)
        else:
            response = s.provider.generate(
                "rule",
                context,
                RuleResponseV6
                if s.stage.prompt_version in {"6", "7", "8"}
                else RuleResponse,
            )
        if s.stage.prompt_version in {"7", "8"} and provenance is None:
            provenance = {
                "coverage": "free_ql_draft",
                "grammar": None,
                "reason": "Outside supported typed eval/SQL/reflected-XSS scope or explicit unconstrained experiment; compilation/development/project gates still apply",
            }
        if s.stage.prompt_version in {"6", "7", "8"}:
            from app.services.rule_output import assign_namespace

            response = assign_namespace(
                response, pack, unique_logic=s.stage.prompt_version == "8"
            )
        save_candidate(s.directory, attempt - 1, response)
        (pack / "provenance.json").write_text(json.dumps(provenance))
        digest = hashlib.sha256((pack / "candidate.json").read_bytes()).hexdigest()
        temporary = pack / "generation-receipt.tmp"
        temporary.write_text(
            json.dumps({"input_digest": input_digest, "candidate_digest": digest})
        )
        temporary.replace(receipt)
        s.repository.active(s.stage_id)
        return {
            "attempt": attempt,
            "draft_ok": False,
            "draft_path": str(pack.relative_to(s.directory)),
            "candidate_digest": digest,
        }

    def _failure(self, state, exc, log):
        s = self.service
        pack = self._pack(state)
        if s.experiment.get("lsp") and (pack / "qlpack.yml").exists():
            (pack / "type_feedback.json").write_text(json.dumps(probe_types(pack)))
        diagnostic = save_diagnostic(pack, exc, log)
        s.repository.update(
            s.stage_id,
            result={
                **s.repository.get(s.stage_id).result,
                "last_diagnostic": diagnostic,
                "draft_attempts": state["attempt"],
            },
        )
        return {"draft_ok": False}

    @staticmethod
    def _fixtures(response):
        return {
            "positive": response.positive.model_dump(),
            "negative": response.negative.model_dump(),
        }

    def compile(self, state):
        self._phase("compile_draft")
        s = self.service
        response, pack = self._load(state), self._pack(state)
        log = pack / "execution.log"
        try:
            if not set(map(str, response.knowledge_ids)).issubset(
                {r["id"] for r in self._knowledge(state)}
            ):
                raise AuditError("模型引用了未检索到的知识片段")
            if s.inputs.strategy != "auto" and response.strategy != s.inputs.strategy:
                raise AuditError("生成策略与用户选择不一致")
            if s.modern and response.purpose != s.inputs.purpose:
                raise AuditError("规则用途与需求不一致")
            if (
                response.strategy == "model"
                or (s.modern and s.inputs.purpose == "framework_model")
            ) and not response.modules:
                raise AuditError("模型补充策略必须包含 .qll 建模模块")
            if s.stage.prompt_version in {"6", "7", "8"}:
                from app.services.rule_output import verify_module_imports

                verify_module_imports(response)
            prepare_query(
                pack,
                s.audit.language,
                response.query,
                response.modules,
                fixed_dependencies(s.audit.language),
            )
            fixtures = self._fixtures(response)
            for kind, fixture in fixtures.items():
                write_fixtures(
                    s.directory / f"fixture-check-{state['attempt'] - 1}" / kind,
                    s.audit.language,
                    fixture,
                )
            if not fixtures["positive"]["expected"] or fixtures["negative"]["expected"]:
                raise AuditError("生成样本必须具有正例预期和空反例预期")
            compile_query(pack, log)
            s.repository.active(s.stage_id)
            return {"draft_ok": True}
        except StageCancelled:
            raise
        except AuditError as exc:
            return self._failure(state, exc, log)

    def develop(self, state):
        self._phase("execute_development")
        s = self.service
        if not (
            s.stage.prompt_version in {"6", "7", "8"} or s.experiment.get("execute_dev")
        ):
            return {"draft_ok": True}
        from app.services.rule_development import execute_development

        try:
            result = execute_development(
                s,
                self._pack(state),
                self._load(state),
                self._fixtures(self._load(state)),
                state["attempt"],
                runner=validate_fixtures,
            )
            s.repository.active(s.stage_id)
            if result["status"] != "passed":
                raise AuditError(
                    "生成样例真实执行不匹配；依据 development_feedback 修正样例或模型"
                )
            return {"draft_ok": True}
        except StageCancelled:
            raise
        except AuditError as exc:
            return self._failure(
                state, exc, self._pack(state) / "development-execution.log"
            )

    def persist(self, state):
        self._phase("save_rule")
        s = self.service
        if not state.get("draft_ok"):
            raise AuditError("未通过的规则候选不能持久化为可审批规则")
        response, pack = self._load(state), self._pack(state)
        development = pack / "development_feedback.json"
        with Session(engine) as session:
            # A checkpoint retry after a committed insert must not create another rule.
            rule = session.exec(
                select(RuleVersion).where(RuleVersion.stage_id == s.stage.id)
            ).one_or_none()
            if rule is None:
                rule = RuleVersion(
                    owner_id=s.audit.owner_id,
                    audit_id=s.audit.id,
                    stage_id=s.stage.id,
                    language=s.audit.language,
                    purpose=s.inputs.purpose if s.modern else "unknown",
                    holdout_id=s.inputs.holdout_id,
                    title=response.title,
                    strategy=response.strategy,
                    query=response.query,
                    modules=response.modules,
                    query_hash=query_digest(response.query, response.modules),
                    dependencies=fixed_dependencies(s.audit.language),
                    fixtures=self._fixtures(response),
                    retrieval=[
                        r
                        for r in self._knowledge(state)
                        if r["id"] in set(map(str, response.knowledge_ids))
                    ],
                    validation={
                        "compile": "passed",
                        "coverage_analysis": response.coverage_analysis,
                        "attempts": state["attempt"],
                        "template_provenance": json.loads(
                            (pack / "provenance.json").read_text()
                        ),
                        "development": json.loads(development.read_text())
                        if development.exists()
                        else None,
                        "project_replay": json.loads(
                            (pack / "project-replay.json").read_text()
                        )
                        if (pack / "project-replay.json").exists()
                        else None,
                        "generation_version": s.stage.prompt_version,
                    },
                )
                session.add(rule)
                session.commit()
                session.refresh(rule)
            elif rule.query_hash != query_digest(
                response.query, response.modules
            ) or rule.fixtures != self._fixtures(response):
                raise AuditError("恢复执行时已保存的规则与当前候选不一致")
            result = {
                "rule_id": str(rule.id),
                "coverage_analysis": response.coverage_analysis,
                "retrieval": rule.retrieval,
            }
        s.repository.update(
            s.stage_id, phase="awaiting_fixture_approval", result=result
        )
        return {"rule_id": result["rule_id"]}

    def replay_project(self, state):
        self._phase("project_single_rule")
        from app.services.rule_project_validation import replay_project

        s, pack = self.service, self._pack(state)
        result = replay_project(s, pack)
        from app.services.context_materials import save_json

        save_json(pack / "project-replay.json", result)
        if (
            result["status"] in {"target_missed", "already_covered"}
            and s.inputs.candidate_id
        ):
            return self._failure(
                state,
                AuditError("单规则补漏未通过；见 project_feedback"),
                pack / "project-execution.log",
            )
        return {"draft_ok": True}

    def exhausted(self, state):
        self.service.repository.active(self.service.stage_id)
        raise AuditError("两次规则编译/契约/开发样例验证均未通过；草稿与日志已保留")
