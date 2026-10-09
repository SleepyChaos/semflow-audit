"""Candidate evidence obligations; rejected citations never weaken a verdict gate."""

from app.adapters.source_inventory import inspectable
from app.domain.audit import AuditError
from app.services.review_classification import implicated_cwes


def validate_assessment(service, assessment, context, targets, evidence):
    identifier = str(assessment.candidate_id)
    if service.stage.prompt_version in {"8", "9", "10"}:
        from app.services.discovery_context import validate_premises

        validate_premises(assessment, targets[identifier], context, evidence)
        # The structured ledger contains explicit source citations too. Retain their
        # union in the top-level record, rather than rejecting a missing duplicate ID.
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

            from app.adapters.operation_evidence import locate_quote
            from app.adapters.python_bindings import location_bindings
            from app.contracts.review import PrimaryLocation

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
                service.evidence.audit.language,
            )
            if any(
                c["binding"] in {"no_static_binding", "unknown_dynamic_scope"}
                for b in location_bindings(service.evidence, [clue])
                for c in b.get("direct_calls", [])
            ):
                raise AuditError("实际操作没有符号绑定，偏移主行号不能绕过危险调用校验")
    if (
        service.stage.prompt_version in {"5", "6", "7", "8", "9", "10"}
        and assessment.assessment == "supported"
        and (
            bool(implicated_cwes(targets[identifier], assessment) & {78, 94, 95})
            if service.stage.prompt_version in {"8", "9", "10"}
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
    if assessment.assessment == "excluded" and not any(
        r["kind"] == "query"
        or (
            r["kind"] == "code"
            and inspectable(
                r["reference"].get("file", ""), service.evidence.audit.language
            )
        )
        for r in counter
    ):
        raise AuditError("排除需要实际源码或查询反证")
