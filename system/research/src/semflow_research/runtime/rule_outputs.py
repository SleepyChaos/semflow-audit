"""Project scientific rule records into immutable public artifacts and receipts."""

import json
from uuid import UUID, uuid5

from semflow_contracts.common import ArtifactRef, canonical_bytes, digest
from semflow_contracts.errors import ResearchError
from semflow_contracts.rule_values import RuleRef
from semflow_contracts.rules import RuleResult
from semflow_contracts.validation import CheckResult, ValidationReceipt

from semflow_research.state.models import RuleVersion


def json_artifact(context, value, version, kind="materials"):
    return context.artifacts.commit(
        canonical_bytes(value), kind=kind, schema_version=version
    )


def export(context, rule_id):
    rule = context.records.get(RuleVersion, UUID(str(rule_id)))

    def stable(data, *, name, **metadata):
        # Peer: approval subject digest / verify_saved_output. AGENT: an
        # ArtifactRef includes its ID, not just its bytes; retain the original
        # references across resume instead of minting identities for equal data.
        memo = context.workspace / "rule-subjects" / str(rule.id) / (name + ".json")
        memo.parent.mkdir(parents=True, exist_ok=True)
        if memo.is_symlink():
            raise ResearchError(
                "integrity_error", "Rule subject pointer cannot be a symlink"
            )
        if memo.exists():
            ref = ArtifactRef.model_validate_json(memo.read_bytes())
            if (
                ref.owner_execution_id != context.execution_id
                or context.artifacts.read(ref) != data
            ):
                raise ResearchError(
                    "approval_stale", "Frozen rule subject bytes changed"
                )
            return ref
        ref = context.artifacts.commit(data, **metadata)
        with memo.open("x") as stream:
            stream.write(ref.model_dump_json())
        return ref

    def stable_json(value, name, version):
        return stable(
            canonical_bytes(value), name=name, kind="materials", schema_version=version
        )

    query = stable(
        rule.query.encode(),
        name="query",
        kind="query",
        schema_version="codeql.query/1",
        media_type="text/plain",
    )
    modules = tuple(
        stable_json(
            {"name": name, "content": content}, "module-" + name, "codeql.module/1"
        )
        for name, content in sorted(rule.modules.items())
    )
    dependencies = stable_json(
        rule.dependencies, "dependencies", "codeql.dependencies/1"
    )
    fixtures = stable_json(rule.fixtures, "fixtures", "codeql.fixtures/1")
    coverage = json_artifact(
        context,
        {"analysis": rule.validation["coverage_analysis"]},
        "semflow.rule-coverage/1",
    )
    retrieval = json_artifact(context, rule.retrieval, "semflow.rule-retrieval/1")
    reference = RuleRef(
        rule_id=rule.id,
        version=context.spec.implementation.method_version,
        purpose=rule.purpose,
        language=rule.language,
        query=query,
        modules=modules,
        dependencies=dependencies,
        query_hash=query.sha256,
    )
    subjects = (query, *modules, dependencies, fixtures)
    checks = [
        receipt(
            context, "rule_compile", {"status": rule.validation["compile"]}, subjects
        )
    ]
    if rule.validation.get("development"):
        checks.append(
            receipt(
                context, "rule_development", rule.validation["development"], subjects
            )
        )
    technical = None
    # Native validation is absent before approval. Development is never promoted
    # into an approved technical check merely because its fixtures passed.
    if rule.fixtures_approved and rule.validation.get("tests") is not None:
        technical = receipt(
            context,
            "rule_development",
            {
                k: rule.validation[k]
                for k in ("status", "tests", "codeql_version", "meaning")
            },
            subjects,
            name="approved_fixtures",
        )
    independent = receipt(
        context,
        "rule_holdout",
        rule.validation.get("independent_holdout")
        or {
            "status": "not_evaluated"
            if context.spec.inputs.acceptance.holdout is None
            else "not_run",
            "meaning": "Independent evaluation is distinct from generated fixture approval and platform publication",
        },
        subjects,
    )
    from semflow_research.runtime.rule_diagnostics import publish

    diagnostics, _ = publish(context, validation=rule.validation, title=rule.title)
    replay = None
    if rule.validation.get("project_replay"):
        raw = rule.validation["project_replay"]
        status = {
            "target_detected": "passed",
            "not_evaluated": "not_evaluated",
            "target_missed": "failed",
            "already_covered": "failed",
            "candidate_match_needs_confirmation": "inconclusive",
            "baseline_match_needs_confirmation": "inconclusive",
        }.get(raw["status"], "error")
        replay = receipt(
            context,
            "rule_project_replay",
            {**raw, "status": status, "matching_status": raw["status"]},
            subjects,
        )
    return RuleResult(
        validation_semantics="semflow.rule-validation/2",
        rule_id=rule.id,
        rule=reference,
        purpose=rule.purpose,
        strategy=rule.strategy,
        coverage_analysis=coverage,
        fixtures=fixtures,
        retrieval_trace=retrieval,
        development_checks=tuple(checks),
        technical_validation=technical,
        independent_validation=independent,
        diagnostics=diagnostics,
        project_replay=replay,
        outcome="checks_passed"
        if technical
        and technical.status == "passed"
        and independent.status == "passed"
        and (replay is None or replay.status in {"passed", "not_evaluated"})
        else "draft",
    )


def receipt(context, kind, raw, subjects, *, name=None):
    ref = json_artifact(context, raw, "semflow.rule-check/1", "validation_receipt")
    status = raw.get("status", "error")
    if status not in {
        "passed",
        "failed",
        "error",
        "not_run",
        "not_evaluated",
        "inconclusive",
        "stale",
    }:
        status = "error"
    return ValidationReceipt(
        validation_id=uuid5(context.execution_id, name or kind),
        kind=kind,
        status=status,
        subject_refs=subjects,
        identity_digest=digest(
            {
                "subjects": [r.model_dump(mode="json") for r in subjects],
                "raw": ref.model_dump(mode="json"),
            }
        ),
        checks=(
            CheckResult(
                check_id=name or kind,
                category=kind,
                status=status,
                observed=ref,
                evidence=(ref,),
            ),
        ),
        tool_profile=context.spec.policy.resource_profile,
        raw_output=ref,
        meaning=raw.get(
            "meaning",
            "Technical check of the exact frozen query and generated fixtures; no platform publication or precision claim",
        ),
    )


def subject_refs(output):
    return (
        output.rule.query,
        *output.rule.modules,
        output.rule.dependencies,
        output.fixtures,
    )


def verify_saved_output(context, previous, rule_id):
    from semflow_contracts.errors import ResearchError

    current = export(context, rule_id)
    if subject_refs(current) != subject_refs(previous):
        raise ResearchError(
            "approval_stale",
            "Saved rule, modules, dependencies or fixtures changed after approval request",
        )
    # Verify original candidate bytes as well; never resume a changed working draft.
    record = context.records.get(RuleVersion, UUID(str(rule_id)))
    pack = context.workspace / f"draft-{record.validation['attempts'] - 1}"
    receipt_path = pack / "generation-receipt.json"
    saved = json.loads(receipt_path.read_bytes())
    import hashlib

    if (
        hashlib.sha256((pack / "candidate.json").read_bytes()).hexdigest()
        != saved["candidate_digest"]
    ):
        raise ResearchError(
            "approval_stale", "Working rule draft changed after approval request"
        )
