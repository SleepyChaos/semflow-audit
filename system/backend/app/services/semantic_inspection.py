"""Bounded read-only semantic preparation with immutable evidence and receipts."""

from app.contracts.semantics import InspectionResponse
from app.domain.audit import AuditError
from app.services.context_materials import (
    deduplicate,
    digest,
    frozen_call,
    project_inventory,
    save_json,
    semantic_policy,
    verify_snapshot,
)


class SemanticInspection:
    def __init__(
        self,
        evidence,
        provider,
        directory,
        repository,
        purpose,
        *,
        progressive=False,
        reference_context=None,
        require_grounded_source=False,
    ):
        self.evidence, self.provider = evidence, provider
        self.directory, self.repository, self.purpose = directory, repository, purpose
        self.policy = semantic_policy(directory)
        self.progressive = progressive
        self.reference_context = reference_context
        self.require_grounded_source = require_grounded_source

    def inspect(
        self,
        targets,
        materials,
        *,
        feedback=None,
        namespace="initial",
        requested_behavior=None,
        repair_scope=None,
    ):
        directory = self.directory / "semantics" / namespace
        inventory = project_inventory(
            self.evidence, read_documents=self.purpose != "repair"
        )
        from app.services.inspection_progress import (
            existing_read,
            progress_feedback,
            read_coverage,
            stable_evidence,
        )

        merge = stable_evidence if self.progressive else deduplicate
        collected = merge(
            [*materials, *[row for row in inventory["documents"] if "id" in row]]
        )
        traces = []
        citation_repair = False
        source_clarification = False
        rejected_tools = []
        last_tool_error = None
        # Tool budget is shared across all repair understanding retries.
        budget_path = self.directory / "semantics" / "tools.json"
        import json

        budget = json.loads(budget_path.read_text()) if budget_path.exists() else []
        baseline = directory / "budget-start.json"
        if not baseline.exists():
            save_json(baseline, {"tools_used_before_namespace": len(budget)})
        starting_budget = json.loads(baseline.read_text())[
            "tools_used_before_namespace"
        ]
        for step in range(self.policy["tool_limit"] + 1):
            self.repository.active(str(self.evidence.stage_id))
            verify_snapshot(self.evidence)
            payload = {
                "phase": "inspect_semantics",
                "targets": targets,
                "inventory": {k: v for k, v in inventory.items() if k != "documents"},
                "available_documents": inventory["documents"]
                if self.purpose == "repair"
                else [],
                "evidence": collected,
                "tool_trace": traces,
                "latest_tool_error": last_tool_error,
                "requested_behavior": requested_behavior,
                "repair_scope": repair_scope,
                "feedback": progress_feedback(feedback, traces)
                if self.progressive
                else feedback,
                "remaining_tools": max(
                    0,
                    self.policy["tool_limit"]
                    - starting_budget
                    - (
                        sum(not t.get("reused", False) for t in traces)
                        if self.progressive
                        else len(traces)
                    ),
                ),
            }
            if self.purpose == "repair":
                from app.services.rule_preparation_context import source_windows

                payload["source_windows"] = source_windows(self.evidence, collected)
                payload["source_coverage"] = read_coverage(payload["source_windows"])
                payload["inspection_boundary"] = {
                    "request": "Confirmed candidate describes the requested repair, not independently proven source facts. Do not require an upstream patch or hidden-test details.",
                    "search": "Search/call results locate source; read_source supplies bodies. Already supplied bodies and EOF are explicit in source_windows.",
                    "implementation_choices": "Choose an evidence-compatible minimal implementation; unknown upstream naming is not a business prerequisite. Preserve known public APIs and unrelated behavior.",
                }
                from app.services.inspection_tools import TOOL_CONTRACT

                payload["tool_contract"] = TOOL_CONTRACT
            if self.reference_context is not None:
                from app.services.rule_preparation_context import source_windows

                payload["rule_reference_context"] = {
                    **self.reference_context,
                    "source_windows": source_windows(self.evidence, collected),
                }
            if self.purpose == "repair":
                from app.adapters.semantic_packing import pack_repair_payload

                payload = pack_repair_payload(payload)
            response = frozen_call(
                self.provider,
                self.purpose,
                payload,
                InspectionResponse,
                directory / f"step-{step}",
                ledger_directory=self.directory,
            )
            self.repository.update(
                str(self.evidence.stage_id), usage=self.provider.usage
            )
            known = {row["id"] for row in collected}
            if self.reference_context:
                known.update(r["id"] for r in self.reference_context["knowledge"])
            invalid = response.action != "tool" and any(
                not set(fact.evidence_ids).issubset(known)
                or (fact.state == "supported" and not fact.evidence_ids)
                for fact in response.facts
            )
            if invalid:
                if citation_repair:
                    raise AuditError("语义结论引用未读取证据或没有原文依据")
                citation_repair = True
                feedback = {
                    "prior_feedback": feedback,
                    "validation_error": "Only use the exact IDs present in evidence. Supported facts need an actually read citation. Reissue the complete interpretation; no new facts or assumed IDs.",
                    "allowed_evidence_ids": sorted(known),
                    "invalid_facts": [
                        f.model_dump(mode="json")
                        for f in response.facts
                        if not set(f.evidence_ids).issubset(known)
                        or (f.state == "supported" and not f.evidence_ids)
                    ],
                    "request_intent": "Cite repair_request evidence only for the stated repair intent. It cannot establish actual behavior or safety; those require code citations. You may request a new source read to resolve critical unknowns.",
                }
                continue
            if response.action != "tool":
                if (
                    self.progressive
                    and self.purpose == "repair"
                    and response.action in {"ready", "insufficient"}
                    and not source_clarification
                    and len(budget) < self.policy["tool_limit"]
                    and any(
                        f.critical
                        and f.state == "unknown"
                        and f.category == "implementation"
                        for f in response.facts
                    )
                ):
                    source_clarification = True
                    feedback = {
                        "prior_feedback": feedback,
                        "unresolved_source_facts": [
                            f.model_dump(mode="json")
                            for f in response.facts
                            if f.critical and f.state == "unknown"
                        ],
                        "instruction": "Before declaring unavailable repository facts, use remaining read-only tools for the named unread implementation or caller. This is one clarification opportunity, not permission to invent business requirements. Return insufficient if business constraints remain unknown after actual source inspection.",
                    }
                    continue
                if response.action != "ready" or any(
                    f.critical and f.state in {"unknown", "conflicting"}
                    for f in response.facts
                ):
                    raise AuditError(
                        "关键业务/漏洞语义证据不足，需补充或人工澄清",
                        code="evidence_insufficient",
                    )
                if not any(
                    row["kind"] == "code"
                    and row["reference"]
                    .get("file", "")
                    .endswith((".py", ".js", ".jsx", ".ts", ".tsx"))
                    for row in collected
                ):
                    raise AuditError("语义理解缺少实际源码正文")
                code_ids = {
                    row["id"]
                    for row in collected
                    if row["kind"] == "code"
                    and row["reference"]
                    .get("file", "")
                    .endswith((".py", ".js", ".jsx", ".ts", ".tsx"))
                }
                if self.require_grounded_source and not any(
                    f.state == "supported" and code_ids.intersection(f.evidence_ids)
                    for f in response.facts
                ):
                    raise AuditError(
                        "语义准备结论缺少实际源码引用", code="evidence_insufficient"
                    )
                result = {
                    "view": response.model_dump(mode="json"),
                    "evidence": collected,
                    "inventory": inventory,
                    "snapshot_hash": self.evidence.audit.snapshot_hash,
                    "verification": "Evidence-grounded LLM interpretation; business constraints not dynamically proved",
                }
                if self.reference_context is not None:
                    result["reference_context_digest"] = digest(self.reference_context)
                    result["reference_knowledge_ids"] = [
                        r["id"] for r in self.reference_context["knowledge"]
                    ]
                save_json(directory / "result.json", result)
                return result
            call = response.tool.model_dump()
            previous = next(
                (
                    b
                    for b in budget
                    if b["call"] == call
                    and b["namespace"] == namespace
                    and b["step"] == step
                ),
                None,
            )
            reused = (
                existing_read(
                    call,
                    collected,
                    traces,
                    file_lengths={
                        row["file"]: row["total_lines"]
                        for row in payload.get("source_windows", [])
                    },
                )
                if self.progressive
                else None
            )
            if reused:
                if sum(t.get("reused", False) for t in traces) >= 2:
                    raise AuditError(
                        "语义取证重复停滞，纠正反馈后仍未推进", code="budget_exhausted"
                    )
                data = reused
            elif previous:
                data = previous["result"]
                if previous.get("result_hash") != digest(data):
                    raise AuditError("读取工具恢复产物已变化")
            else:
                if len(budget) >= self.policy["tool_limit"]:
                    raise AuditError("源码补证预算耗尽", code="budget_exhausted")
                if any(
                    t["name"] == call["name"] and t["arguments"] == call["arguments"]
                    for t in traces
                ):
                    raise AuditError("语义取证重复停滞，需明确缺失事实")
                try:
                    data = self.read_tool(call)
                except AuditError as error:
                    if not (
                        self.progressive and self.purpose == "repair"
                    ) or error.code in {"integrity_error", "identity_error"}:
                        raise
                    if call in rejected_tools:
                        raise AuditError(
                            "修复取证重复无效请求，需更正参数或范围",
                            code="invalid_tool_request",
                        ) from error
                    rejected_tools.append(call)
                    last_tool_error = {
                        "requested": call,
                        "status": "not_read",
                        "reason": str(error),
                        "instruction": "No evidence was read. Correct the tool arguments using tool_contract; do not cite an absent body or retry the same rejected request.",
                    }
                    continue
                last_tool_error = None
                budget.append(
                    {
                        "namespace": namespace,
                        "step": step,
                        "call": call,
                        "result": data,
                        "result_hash": digest(data),
                    }
                )
                save_json(budget_path, budget)
            traces.append(
                {
                    "name": call["name"],
                    "arguments": call["arguments"],
                    "evidence_id": data["id"],
                    "read_adjustment": data.get("read_adjustment"),
                    **(
                        {
                            "reused": bool(reused),
                            "observation": {
                                **{
                                    key: data[key]
                                    for key in ("id", "kind", "reference", "digest")
                                },
                                "body_field": "evidence[id=" + data["id"] + "].content",
                            },
                        }
                        if self.progressive
                        else {}
                    ),
                }
            )
            collected = merge([*collected, data])
        raise AuditError("语义理解预算耗尽", code="budget_exhausted")

    def read_tool(self, call):
        from app.services.inspection_tools import read_page

        operations = {
            "read_source": lambda **args: read_page(self.evidence, "read_source", args),
            "search_source": self.evidence.search,
            "callers": self.evidence.callers,
            "read_document": lambda **args: read_page(
                self.evidence, "read_document", args
            ),
        }
        try:
            return operations[call["name"]](**call["arguments"])
        except (TypeError, KeyError) as exc:
            raise AuditError("只读取证工具参数无效") from exc
