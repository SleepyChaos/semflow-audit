"""Single-query replay, conservative root matching and immutable baseline identity."""

import json
from uuid import UUID

import yaml
from sqlmodel import Session

from app.adapters.artifacts import ArtifactStore
from app.adapters.codeql.custom import query_digest, run_query
from app.adapters.codeql.sarif import parse_sarif
from app.adapters.codeql.scanner import CodeQLScanner
from app.adapters.snapshot import snapshot_digest
from app.core.db import engine
from app.domain.audit import AuditError
from app.persistence.stage_models import Candidate
from app.services.context_materials import digest, save_json


def overlaps(location, expected):
    return location.get("file") == expected.get("file") and location.get(
        "line", 0
    ) <= expected.get("line", 0) <= location.get("end_line", location.get("line", 0))


def cwe_matches(finding, weakness):
    try:
        number = int(weakness.split("-")[1])
    except ValueError, IndexError:
        return False
    return any(
        tag.lower().endswith(f"cwe-{number:03d}")
        or tag.lower().endswith(f"cwe-{number}")
        for tag in finding.get("tags", [])
    )


def root_candidates(findings, target):
    return [
        f
        for f in findings
        if cwe_matches(f, target.weakness)
        and any(overlaps(loc, target.location) for loc in f["locations"])
    ]


def replay_project(service, pack):
    audit = service.audit
    root = ArtifactStore().source(str(audit.source_run_id))
    base = ArtifactStore().directory(str(audit.id))
    if audit.status != "completed" or snapshot_digest(root) != audit.snapshot_hash:
        raise AuditError("原扫描失败或源码身份变化；不能作为漏检基线")
    if (
        not (base / "database/codeql-database.yml").is_file()
        or not (base / "results.sarif").is_file()
    ):
        raise AuditError("缺少原扫描数据库或原始 SARIF，不能声称补漏")
    if CodeQLScanner().version() != audit.codeql_version:
        raise AuditError("CodeQL 版本变化，需冻结一致的复测环境")
    baseline = parse_sarif(base / "results.sarif", audit.snapshot_hash)
    # Custom baseline findings are already persisted with the audit.
    if not {f["id"] for f in baseline}.issubset({f["id"] for f in audit.findings}):
        raise AuditError("原始 SARIF 与审计基线记录不一致")
    query = (pack / "generated.ql").read_text()
    modules = {p.name: p.read_text() for p in pack.glob("*.qll")}
    identity = {
        "audit": str(audit.id),
        "input_hash": digest(service.stage.inputs),
        "snapshot": audit.snapshot_hash,
        "query_hash": query_digest(query, modules),
        "lock_hash": digest((pack / "codeql-pack.lock.yml").read_text()),
        "dependency_hash": digest(
            yaml.safe_load((pack / "codeql-pack.lock.yml").read_text())["dependencies"]
        ),
        "baseline_hash": digest(audit.findings),
        "custom_rules": audit.custom_rule_ids,
        "cli": audit.codeql_version,
        "query_pack": audit.query_pack,
        "database_metadata_hash": digest(
            (base / "database/codeql-database.yml").read_text()
        ),
    }
    with Session(engine) as db:
        target = (
            db.get(Candidate, service.inputs.candidate_id)
            if service.inputs.candidate_id
            else None
        )
    if target and (target.audit_id != audit.id or target.status != "confirmed"):
        raise AuditError("原项目补漏目标确认状态已变化")
    identity["target_hash"] = digest(target.model_dump(mode="json")) if target else None
    from app.services.rule_database_identity import verify_database

    files = [target.location["file"]] if target else service.inputs.source_paths
    identity["coverage"] = verify_database(base / "database", root, audit, files)
    saved = pack / "project-replay.json"
    if saved.exists():
        result = json.loads(saved.read_text())
        if result.get("identity") != identity or result.get("findings_hash") != digest(
            result.get("findings")
        ):
            raise AuditError("单规则复测产物身份变化")
        return result
    findings = run_query(
        base / "database",
        pack,
        pack / "project.sarif",
        pack / "project-execution.log",
        audit.snapshot_hash,
    )
    if snapshot_digest(root) != audit.snapshot_hash:
        raise AuditError("单规则执行时原始快照变化")
    matched = root_candidates(findings, target) if target else []
    previous = root_candidates(audit.findings, target) if target else []
    status = "not_evaluated" if not target else "target_missed"
    if target and target.static_finding_id:
        previous.extend(
            f for f in audit.findings if f["id"] == target.static_finding_id
        )
    if (
        target
        and matched
        and target.static_finding_id
        and any(f["id"] == target.static_finding_id for f in audit.findings)
    ):
        status = "already_covered"
    elif previous and matched:
        status = "baseline_match_needs_confirmation"
    elif matched:
        # Location/CWE are candidate associations, not proof of the same root path.
        status = "candidate_match_needs_confirmation"
    result = {
        "status": status,
        "identity": identity,
        "findings": findings,
        "findings_hash": digest(findings),
        "matched_ids": [f["id"] for f in matched],
        "baseline_matching_ids": sorted({f["id"] for f in previous}),
        "extra_unresolved_ids": [f["id"] for f in findings if f not in matched],
        "meaning": "CWE/location match requires human root/path confirmation; extra alerts remain unresolved",
    }
    save_json(saved, result)
    return result


def confirm_project_match(
    rule, finding_id, actor_id, reason, baseline_exclusion_reason=None
):
    result = rule.validation.get("project_replay") or {}
    if result.get("status") not in {
        "candidate_match_needs_confirmation",
        "baseline_match_needs_confirmation",
        "already_covered",
    } or finding_id not in result.get("matched_ids", []):
        raise AuditError("请选择单规则复测中对应目标的待确认结果")
    baseline_reuse = result["status"] == "already_covered"
    if (
        result.get("baseline_matching_ids")
        and not baseline_reuse
        and not baseline_exclusion_reason
    ):
        raise AuditError("需说明原基线相近结果为何不是此目标根因")
    if result.get("findings_hash") != digest(result.get("findings")):
        raise AuditError("单规则结果内容已变化")
    with Session(engine) as db:
        # Confirm the original candidate is still confirmed, using the stage input.
        from app.persistence.stage_models import StageRun

        stage = db.get(StageRun, rule.stage_id)
        target = db.get(Candidate, UUID(stage.inputs["candidate_id"]))
    if (
        target is None
        or target.status != "confirmed"
        or digest(target.model_dump(mode="json")) != result["identity"]["target_hash"]
    ):
        raise AuditError("目标确认记录变化，需重新验证")
    rule.validation = {
        **rule.validation,
        "project_replay": {
            **result,
            "status": "target_detected",
            "coverage": "baseline_reuse" if baseline_reuse else "root_confirmed",
            "confirmation": {
                "actor_id": str(actor_id),
                "finding_id": finding_id,
                "reason": reason,
                "baseline_exclusion_reason": baseline_exclusion_reason,
            },
        },
    }


def check_project_validation(rule):
    from app.persistence.audit_models import AuditRun
    from app.persistence.stage_models import StageRun

    result = rule.validation.get("project_replay") or {}
    if result.get("status") not in {"target_detected", "not_evaluated"}:
        raise AuditError("规则发布需要原项目单规则复测及目标根因确认")
    identity = result.get("identity") or {}
    required = {
        "dependency_hash",
        "query_hash",
        "baseline_hash",
        "snapshot",
        "cli",
        "query_pack",
        "database_metadata_hash",
        "target_hash",
        "input_hash",
        "custom_rules",
    }
    if not required.issubset(identity) or not {"findings", "findings_hash"}.issubset(
        result
    ):
        raise AuditError("单规则复测身份不完整，需按当前流程重新验证")
    if identity["dependency_hash"] != digest(rule.dependencies):
        raise AuditError("规则依赖锁已变化")
    if (
        identity["query_hash"] != query_digest(rule.query, rule.modules)
        or identity["query_hash"] != rule.query_hash
        or result["findings_hash"] != digest(result["findings"])
    ):
        raise AuditError("单规则复测结果已失效")
    with Session(engine) as db:
        audit = db.get(AuditRun, rule.audit_id)
        stage = db.get(StageRun, rule.stage_id)
        target = (
            db.get(Candidate, UUID(stage.inputs["candidate_id"]))
            if stage.inputs.get("candidate_id")
            else None
        )
    if (
        audit is None
        or digest(audit.findings) != identity["baseline_hash"]
        or snapshot_digest(ArtifactStore().source(str(audit.source_run_id)))
        != identity["snapshot"]
    ):
        raise AuditError("原项目基线或快照变化")
    if (
        audit.codeql_version != identity["cli"]
        or audit.query_pack != identity["query_pack"]
        or CodeQLScanner().version() != identity["cli"]
    ):
        raise AuditError("CodeQL 执行环境变化")
    metadata = ArtifactStore().directory(str(audit.id)) / "database/codeql-database.yml"
    if (
        not metadata.is_file()
        or digest(metadata.read_text()) != identity["database_metadata_hash"]
    ):
        raise AuditError("原项目数据库身份变化")
    if target and (
        target.status != "confirmed"
        or digest(target.model_dump(mode="json")) != identity["target_hash"]
    ):
        raise AuditError("目标确认记录变化")
    if (
        digest(stage.inputs) != identity["input_hash"]
        or audit.custom_rule_ids != identity["custom_rules"]
    ):
        raise AuditError("目标输入或已发布基线规则组合变化")
    if (target is not None) != (result["status"] == "target_detected"):
        raise AuditError("补漏验证状态与目标不符")
