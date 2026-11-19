"""Algorithm extracted from app.services.review_verdict_gate.

Runtime dependencies are passed explicitly; no platform ORM or configuration.
Changes to JSON require checking the corresponding semflow_contracts/wire peer.
"""

"""Candidate evidence obligations; rejected citations never weaken a verdict gate."""
from semflow_research.adapters.source_inventory import inspectable
from semflow_research.discovery.review_classification import implicated_cwes
from semflow_research.domain.errors import AuditError


def validate_assessment(service, assessment, context, targets, evidence):
    identifier = str(assessment.candidate_id)
    if context.get("evidence_gap_contract"):
        from semflow_research.discovery.review_target_scope import (
            guard_template_state_integrity,
        )

        guard_template_state_integrity(
            assessment, targets[identifier], context["language"], evidence
        )
    if context.get("feedback_revision") and assessment.assessment == "pending":
        raise AuditError("补证必须给出已校验判断或保留insufficient，不能退回未评估")
    detail = getattr(assessment, "detail", None)
    if detail is not None:
        from semflow_research.discovery.review_presentation import validate_detail

        validate_detail(assessment, evidence, require_chinese=False)
    if service.execution.method_version in {"8", "9", "10", "11", "12"}:
        from semflow_research.discovery.discovery_context import validate_premises

        validate_premises(assessment, targets[identifier], context, evidence)
        if context.get("evidence_gap_contract"):
            from semflow_research.discovery.review_target_scope import (
                guard_operation_scope,
            )

            guard_operation_scope(
                service.evidence, targets[identifier], assessment, evidence
            )
        cited = list(
            dict.fromkeys(
                [
                    *assessment.evidence_ids,
                    *[
                        identifier
                        for premise in assessment.premises
                        for identifier in premise.evidence_ids
                    ],
                ]
            )
        )
        if len(cited) > 30:
            raise AuditError("前提证据总量超过候选上限；需聚焦真实证明路径")
        assessment.evidence_ids = cited
        if assessment.assessment == "supported" and implicated_cwes(
            targets[identifier], assessment
        ) & {78, 94, 95}:
            from types import SimpleNamespace

            from semflow_contracts.modelio.review import PrimaryLocation

            from semflow_research.adapters.operation_evidence import locate_quote
            from semflow_research.adapters.python_bindings import location_bindings

            operation = next(p for p in assessment.premises if p.premise == "operation")
            clue = locate_quote(
                SimpleNamespace(
                    primary_location=PrimaryLocation.model_validate(
                        {
                            k: targets[identifier]["location"][k]
                            for k in ("file", "line")
                        }
                    ),
                    operation_quote=operation.quote,
                    evidence_ids=operation.evidence_ids,
                ),
                context,
                service.evidence.source_context.language,
            )
            if any(
                c["binding"] in {"no_static_binding", "unknown_dynamic_scope"}
                for b in location_bindings(service.evidence, [clue])
                for c in b.get("direct_calls", [])
            ):
                raise AuditError("实际操作没有符号绑定，偏移主行号不能绕过危险调用校验")
    if (
        service.execution.method_version in {"5", "6", "7", "8", "9", "10", "11", "12"}
        and assessment.assessment == "supported"
        and (
            bool(implicated_cwes(targets[identifier], assessment) & {78, 94, 95})
            if service.execution.method_version in {"8", "9", "10", "11", "12"}
            else assessment.weakness
            in {"CWE-78", "CWE-078", "CWE-94", "CWE-094", "CWE-95", "CWE-095"}
        )
    ):
        location = targets[identifier]["location"]
        for binding in context.get("symbol_bindings", []):
            if (
                binding.get("file") == location["file"]
                and binding.get("line") == location["line"]
                and any(
                    c["binding"] in {"no_static_binding", "unknown_dynamic_scope"}
                    for c in binding.get("direct_calls", [])
                )
            ):
                raise AuditError(
                    "危险调用没有静态符号绑定，不得假设为导入API；需核实动态绑定或保留证据不足"
                )
    evidence(
        assessment.evidence_ids,
        targets[identifier]["location"]
        if assessment.assessment in {"supported", "excluded"}
        else None,
    )
    counter = evidence(assessment.counterevidence_ids)
    if assessment.assessment == "excluded" and (
        not any(
            r["kind"] == "query"
            or (
                r["kind"] == "code"
                and inspectable(
                    r["reference"].get("file", ""),
                    service.evidence.source_context.language,
                )
            )
            for r in counter
        )
    ):
        raise AuditError("排除需要实际源码或查询反证")
