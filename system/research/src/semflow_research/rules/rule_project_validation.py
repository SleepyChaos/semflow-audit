"""Algorithm extracted from app.services.rule_project_validation.

Runtime dependencies are passed explicitly; no platform ORM or configuration.
Changes to JSON require checking the corresponding semflow_contracts/wire peer.
"""

"""Single-query replay, conservative root matching and immutable baseline identity."""
import json
import shutil
from pathlib import Path

import yaml

from semflow_research.adapters.artifacts import ArtifactStore
from semflow_research.adapters.codeql.custom import query_digest, run_query
from semflow_research.adapters.codeql.sarif import parse_sarif
from semflow_research.adapters.codeql.scanner import CodeQLScanner
from semflow_research.adapters.snapshot import snapshot_digest
from semflow_research.domain.errors import AuditError
from semflow_research.evidence.context_materials import digest, save_json
from semflow_research.state.models import Candidate


def overlaps(location, expected):
    return location.get("file") == expected.get("file") and location.get(
        "line", 0
    ) <= expected.get("line", 0) <= location.get("end_line", location.get("line", 0))


def cwe_matches(finding, weakness):
    try:
        number = int(weakness.split("-")[1])
    except (ValueError, IndexError):
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


def replay_project(service, pack, *, _kernel):
    audit = service.source_context
    root = ArtifactStore(_kernel=_kernel).source(str(audit.snapshot_id))
    base = ArtifactStore(_kernel=_kernel).directory(str(audit.id))
    if audit.status != "completed" or snapshot_digest(root) != audit.snapshot_hash:
        raise AuditError("原扫描失败或源码身份变化；不能作为漏检基线")
    if (
        not (base / "database/codeql-database.yml").is_file()
        or not (base / "results.sarif").is_file()
    ):
        raise AuditError("缺少原扫描数据库或原始 SARIF，不能声称补漏")
    if CodeQLScanner(_kernel=_kernel).version() != audit.codeql_version:
        raise AuditError("CodeQL 版本变化，需冻结一致的复测环境")
    baseline = parse_sarif(base / "results.sarif", audit.snapshot_hash)
    if not {f["id"] for f in baseline}.issubset({f["id"] for f in audit.findings}):
        raise AuditError("原始 SARIF 与审计基线记录不一致")
    query = (pack / "generated.ql").read_text()
    modules = {p.name: p.read_text() for p in pack.glob("*.qll")}
    identity = {
        "audit": str(audit.id),
        "input_hash": digest(service.execution.inputs),
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
    with _kernel.records.transaction() as db:
        target = (
            db.get(Candidate, service.inputs.candidate_id)
            if service.inputs.candidate_id
            else None
        )
    if target and (target.snapshot_id != audit.id or target.status != "confirmed"):
        raise AuditError("原项目补漏目标确认状态已变化")
    identity["target_hash"] = digest(target.model_dump(mode="json")) if target else None
    from semflow_research.rules.rule_database_identity import verify_database

    files = [target.location["file"]] if target else service.inputs.source_paths
    identity["coverage"] = verify_database(
        base / "database",
        root,
        audit,
        files,
        original_source_root=_kernel.spec.inputs.development.static_baseline.original_source_root,
    )
    saved = pack / "project-replay.json"
    if saved.exists():
        result = json.loads(saved.read_text())
        if result.get("identity") != identity or result.get("findings_hash") != digest(
            result.get("findings")
        ):
            raise AuditError("单规则复测产物身份变化")
        return result
    database = pack / "project-database"
    if database.exists():
        raise AuditError(
            "Previous project replay has an unknown outcome; preserve it and create a new execution",
            code="external_outcome_unknown",
        )
    shutil.copytree(base / "database", database)
    findings = run_query(
        database,
        pack,
        pack / "project.sarif",
        pack / "project-execution.log",
        audit.snapshot_hash,
        _kernel=_kernel,
    )
    prefix = _kernel.spec.inputs.development.static_baseline.original_source_root
    for finding in findings:
        for point in [
            *finding["locations"],
            *[p for flow in finding["code_flows"] for p in flow],
        ]:
            if Path(point["file"]).is_absolute():
                point["file"] = Path(point["file"]).relative_to(prefix).as_posix()
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
        and target.static_finding_id
        and any(f["id"] == target.static_finding_id for f in audit.findings)
    ):
        status = "already_covered"
    elif previous and matched:
        status = "baseline_match_needs_confirmation"
    elif matched:
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
