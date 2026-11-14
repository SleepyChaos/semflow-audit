"""Project immutable rule receipts; platform decisions remain platform-owned."""

from uuid import uuid5

from semflow_research.public.rule_results import read_projection
from sqlmodel import select

from app.adapters.codeql.custom import query_digest
from app.domain.audit import AuditError
from app.models import get_datetime_utc
from app.persistence.audit_models import AuditRun
from app.persistence.knowledge_models import RuleVersion
from app.persistence.stage_models import StageRun
from app.research_bridge.protocol import verify_receipt
from app.research_bridge.rule_integrity import verify_confirmation


def project_rule(session, binding, envelope, *, root):
    # WIRE-RECV:research.result — peer: rule_outputs.export / public.rule_results.
    # AGENT: scientific query_hash covers query bytes. The legacy DTO hash below
    # covers query+modules; retain both and never infer publication from completion.
    stage = session.exec(
        select(StageRun).where(StageRun.id == binding.stage_id).with_for_update()
    ).one()
    audit = session.get(AuditRun, stage.audit_id)
    envelope = verify_receipt(binding, audit, envelope)
    marker = {
        key: value
        for key, value in stage.result.items()
        if key.startswith("research_input_") or key.startswith("research_platform_")
    }
    if binding.manifest == envelope.manifest.model_dump(mode="json"):
        return stage
    verify_confirmation(session, stage)
    body = envelope.result
    published_rule = None
    if body is not None:
        if body.validation_semantics != "semflow.rule-validation/2":
            raise AuditError(
                "旧规则技术状态不得按新版独立验收语义投影", code="unsupported_version"
            )
        view = read_projection(envelope, root=root)
        if binding.manifest is not None and (
            view.previous_manifest is None
            or view.previous_manifest.model_dump(mode="json") != binding.manifest
        ):
            raise AuditError("规则科研清单不在原批准链上", code="integrity_error")
        key = f"{binding.execution_id}/{body.rule_id}"
        identifier = uuid5(stage.id, key)
        if key in binding.entity_map and binding.entity_map[key] != str(identifier):
            raise AuditError("规则平台身份映射变化", code="integrity_error")
        rule = session.get(RuleVersion, identifier)
        if rule is None:
            rule = RuleVersion(
                id=identifier,
                owner_id=audit.owner_id,
                audit_id=audit.id,
                stage_id=stage.id,
                language=body.rule.language,
                title=view.title,
                purpose=body.purpose,
                strategy=body.strategy,
                query=view.query,
                query_hash=query_digest(view.query, view.modules),
                modules=view.modules,
                dependencies=view.dependencies,
                fixtures=view.fixtures,
                holdout_id=stage.inputs.get("holdout_id"),
                retrieval=view.retrieval,
            )
        elif (rule.query, rule.modules, rule.dependencies, rule.fixtures) != (
            view.query,
            view.modules,
            view.dependencies,
            view.fixtures,
        ):
            raise AuditError("已有规则与冻结产物不同", code="integrity_error")
        validation = dict(view.validation)
        if validation.get("project_replay"):
            from app.research_bridge.rule_views import project_replay

            validation["project_replay"] = project_replay(
                session, stage, audit, validation["project_replay"]
            )
        validation.update(
            research_manifest=envelope.manifest.model_dump(mode="json"),
            research_result=body.model_dump(mode="json"),
            research_query_sha256=body.rule.query_hash,
        )
        rule.validation = validation
        rule.retrieval = [
            {
                **row,
                "research_id": row["id"],
                "id": binding.entity_map.get("knowledge/" + row["id"], row["id"]),
            }
            for row in view.retrieval
        ]
        if rule.status not in {"published", "retired"}:
            rule.status = (
                "validated"
                if rule.fixtures_approved and body.outcome == "checks_passed"
                else "draft"
            )
        binding.entity_map = {**binding.entity_map, key: str(identifier)}
        session.add(rule)
        published_rule = rule
    stage.status = (
        "awaiting_confirmation"
        if envelope.execution_status == "awaiting_input"
        else envelope.execution_status
    )
    stage.error = envelope.failure.message if envelope.failure else None
    stage.phase = (
        "awaiting_fixture_approval"
        if envelope.pending_action
        else "rule_validation_ready"
        if published_rule
        else "rule_failed"
    )
    stage.usage = envelope.usage.model_dump(mode="json")
    stage.result = {
        **marker,
        "research_receipt": {
            "execution_id": str(envelope.execution_id),
            "manifest": envelope.manifest.model_dump(mode="json"),
        },
        "failure": envelope.failure.model_dump(mode="json")
        if envelope.failure
        else None,
        **(
            {"rule_id": str(published_rule.id), "validation": published_rule.validation}
            if published_rule
            else {}
        ),
    }
    stage.updated_at = get_datetime_utc()
    binding.manifest = envelope.manifest.model_dump(mode="json")
    session.add(binding)
    session.add(stage)
    session.commit()
    session.refresh(stage)
    return stage
