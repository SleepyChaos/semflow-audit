"""Algorithm extracted from app.services.review.

Runtime dependencies are passed explicitly; no platform ORM or configuration.
Changes to JSON require checking the corresponding semflow_contracts/wire peer.
"""

"""Bounded evidence-driven review; model conclusions never become human confirmations."""
import hashlib
import json

from semflow_contracts.modelio.review import ReviewResponseV2
from semflow_contracts.modelio.stages import ReviewRequest, ReviewResponse

from semflow_research.discovery.review_results import save_v2
from semflow_research.domain.errors import AuditError
from semflow_research.evidence.evidence import EvidenceService, valid_evidence
from semflow_research.ports.model import ModelProvider
from semflow_research.state.models import Candidate


class ReviewService:
    def __init__(self, execution_id: str, provider: ModelProvider, *, _kernel):
        self._kernel = _kernel
        self.execution_id, self.provider = (execution_id, provider)
        self.repository = _kernel.execution_records
        self.execution = self.repository.get(execution_id)
        self.inputs = ReviewRequest.model_validate(self.execution.inputs)
        self.evidence = EvidenceService(
            str(self.execution.snapshot_id),
            execution_id,
            self.inputs.paths,
            _kernel=_kernel,
        )

    def prepare(self) -> dict:
        _kernel = self._kernel
        self.repository.update(
            self.execution_id, phase="prepare", model=self.provider.model
        )
        audit = self.evidence.source_context
        targets, collected = ([], [])
        findings = audit.findings
        if self.inputs.finding_ids:
            if not set(self.inputs.finding_ids).issubset(
                {item["id"] for item in findings}
            ):
                raise AuditError("复审告警 ID 不属于本次扫描")
            findings = [
                item for item in findings if item["id"] in self.inputs.finding_ids
            ]
        with _kernel.records.transaction() as session:
            for finding in findings:
                location = finding["locations"][0]
                try:
                    source = self.evidence.read(
                        location["file"],
                        max(1, location["line"] - 8),
                        location["line"] + 12,
                    )
                except AuditError:
                    if self.inputs.paths and (not self.inputs.finding_ids):
                        continue
                    raise
                if source["id"] not in {row["id"] for row in collected}:
                    collected.append(source)
                candidate = Candidate(
                    snapshot_id=audit.id,
                    execution_id=self.execution.id,
                    origin="static",
                    static_finding_id=finding["id"],
                    identity_key="static:" + finding["id"],
                    novelty="baseline",
                    location=location,
                    title=finding["rule"],
                    description=finding["message"],
                    evidence_ids=[source["id"]],
                )
                session.save(candidate)
                targets.append(
                    {
                        "candidate_id": str(candidate.id),
                        "static_alert": finding,
                        "evidence_id": source["id"],
                    }
                )
            session.commit()
        anchors = self.evidence.anchors() if self.inputs.discover else []
        if not targets and (not anchors):
            raise AuditError("所选范围没有可复审告警或安全操作锚点；请明确目标范围")
        context = {
            "snapshot": audit.snapshot_hash,
            "language": audit.language,
            "paths": self.inputs.paths,
            "targets": targets,
            "anchors": anchors,
            "evidence": collected,
            "tool_trace": [],
            "model_recommendations_only": True,
        }
        if len(json.dumps(context, ensure_ascii=False)) > self.inputs.max_context_chars:
            raise AuditError("初始证据超过上下文预算，请减少复审目标")
        return {"context": context, "steps": 0}

    def reason(self, state: dict) -> dict:
        self.repository.active(self.execution_id)
        if state["steps"] >= self.inputs.max_steps:
            raise AuditError("AI 取证步数预算耗尽；未自动排除或确认任何漏洞")
        self.repository.update(self.execution_id, phase="reason")
        schema = (
            ReviewResponseV2
            if self.execution.method_version in {"2", "3"}
            else ReviewResponse
        )
        response = self.provider.generate("review", state["context"], schema)
        self.repository.update(self.execution_id, usage=self.provider.usage)
        if (
            self.execution.method_version == "1"
            and response.action == "tool"
            and (response.tool is None or response.findings)
        ):
            raise AuditError("模型工具请求契约无效")
        if response.action == "final" and response.tool is not None:
            raise AuditError("模型最终结论不能包含未执行的工具请求")
        return {
            "response": response.model_dump(mode="json"),
            "steps": state["steps"] + 1,
        }

    def gather(self, state: dict) -> dict:
        _kernel = self._kernel
        self.repository.active(self.execution_id)
        call = state["response"]["tool"]
        arguments = call["arguments"]
        name = call["name"]
        if name == "read_source":
            data = self.evidence.read(**arguments)
        elif name == "search_source":
            data = self.evidence.search(**arguments)
        elif name == "callers":
            data = self.evidence.callers(**arguments)
        elif name == "knowledge":
            from semflow_research.rules.knowledge_evidence import gather_knowledge

            data = gather_knowledge(
                self.evidence,
                state["context"],
                self.inputs.max_context_chars,
                arguments["query"],
                _kernel=_kernel,
            )
        elif name == "static_query":
            from semflow_research.rules.rules_execution import execute_evidence_query

            count = sum(
                row["tool"] == "static_query" for row in state["context"]["tool_trace"]
            )
            if count >= _kernel.settings.REVIEW_QUERY_LIMIT:
                raise AuditError("静态取证查询预算已耗尽")
            data = execute_evidence_query(self.evidence, arguments["rule_id"])
        else:
            raise AuditError("不支持的取证工具")
        context = {
            **state["context"],
            "evidence": state["context"]["evidence"]
            if data["id"] in {row["id"] for row in state["context"]["evidence"]}
            else [*state["context"]["evidence"], data],
            "tool_trace": [
                *state["context"]["tool_trace"],
                {"tool": name, "arguments": arguments, "evidence_id": data["id"]},
            ],
        }
        if len(json.dumps(context, ensure_ascii=False)) > self.inputs.max_context_chars:
            raise AuditError(
                "上下文取证预算耗尽；请请求更窄的源码页", code="context_budget"
            )
        self.repository.update(
            self.execution_id,
            phase="evidence",
            result={
                **self.repository.get(self.execution_id).result,
                "trace": context["tool_trace"],
                "anchors": context["anchors"],
            },
        )
        return {"context": context}

    def save(self, state: dict) -> dict:
        _kernel = self._kernel
        self.repository.active(self.execution_id)
        if self.execution.method_version in {"2", "3"}:
            try:
                return save_v2(self, state, _kernel=_kernel)
            except AuditError as exc:
                exc.code = "evidence_invalid"
                raise
        response = ReviewResponse.model_validate(state["response"])
        evidence_ids = {row["id"] for row in state["context"]["evidence"]}
        target_ids = {row["candidate_id"] for row in state["context"]["targets"]}
        saved = []
        with _kernel.records.transaction() as session:
            for proposal in response.findings:
                identifiers = [str(identifier) for identifier in proposal.evidence_ids]
                if not set(identifiers).issubset(evidence_ids):
                    raise AuditError("模型引用了未取到的证据")
                if proposal.assessment in {"supported", "excluded"}:
                    valid_evidence(
                        self.execution.snapshot_id,
                        proposal.evidence_ids,
                        _kernel=_kernel,
                    )
                if proposal.candidate_id:
                    if str(proposal.candidate_id) not in target_ids:
                        raise AuditError("模型试图覆盖目标之外的候选")
                    candidate = session.get(Candidate, proposal.candidate_id)
                else:
                    if not self.inputs.discover:
                        raise AuditError("当前复审未授权提出补充发现")
                    location = proposal.primary_location
                    if (
                        not isinstance(location, dict)
                        or set(location) != {"file", "line"}
                        or (not isinstance(location["line"], int))
                    ):
                        raise AuditError("补充发现需要真实的主位置 file/line")
                    self.evidence.allowed(location["file"])
                    rows = valid_evidence(
                        self.execution.snapshot_id,
                        proposal.evidence_ids,
                        _kernel=_kernel,
                    )
                    if not any(
                        row.kind == "code"
                        and row.reference.get("file") == location["file"]
                        and (
                            row.reference["start_line"]
                            <= location["line"]
                            <= row.reference["end_line"]
                        )
                        for row in rows
                    ):
                        raise AuditError("补充发现主位置必须落在已取得的源码证据内")
                    targets = target_ids | {
                        anchor["id"] for anchor in state["context"]["anchors"]
                    }
                    if proposal.related_target not in targets:
                        raise AuditError("补充发现需要关联真实复审目标或安全操作锚点")
                    overlapping = any(
                        item["file"] == location["file"]
                        and item["line"] == location["line"]
                        for finding in self.evidence.source_context.findings
                        for item in finding["locations"]
                    )
                    identity = hashlib.sha256(
                        json.dumps(
                            [
                                self.evidence.source_context.snapshot_hash,
                                location,
                                proposal.weakness,
                            ],
                            sort_keys=True,
                        ).encode()
                    ).hexdigest()
                    candidate = Candidate(
                        snapshot_id=self.execution.snapshot_id,
                        execution_id=self.execution.id,
                        origin="ai",
                        title=proposal.title,
                        description=proposal.description,
                        identity_key="ai:" + identity,
                        location=location,
                        novelty="overlaps_static" if overlapping else "new_location",
                    )
                candidate.title, candidate.description = (
                    proposal.title,
                    proposal.description,
                )
                candidate.evidence_ids = identifiers
                candidate.status = (
                    "insufficient"
                    if proposal.assessment == "insufficient"
                    else "pending"
                )
                candidate.related_target = proposal.related_target
                session.save(candidate)
                saved.append(
                    {"id": str(candidate.id), "recommendation": proposal.assessment}
                )
            session.commit()
            missing = session.list(Candidate, execution_id=self.execution.id)
        result = {
            "summary": response.summary,
            "recommendations": saved,
            "candidate_ids": [str(row.id) for row in missing],
            "trace": state["context"]["tool_trace"],
            "anchors": state["context"]["anchors"],
            "snapshot_hash": self.evidence.source_context.snapshot_hash,
            "reviewed_static_finding_ids": [
                row["static_alert"]["id"] for row in state["context"]["targets"]
            ],
            "unreviewed_static_finding_ids": [
                row["id"]
                for row in self.evidence.source_context.findings
                if row["id"]
                not in {
                    target["static_alert"]["id"]
                    for target in state["context"]["targets"]
                }
            ],
        }
        self.repository.update(
            self.execution_id,
            status="completed",
            phase="awaiting_human_decisions",
            result=result,
        )
        return {"saved": True}
