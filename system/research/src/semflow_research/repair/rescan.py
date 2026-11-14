"""Original native rescan judgment over explicit original and patched scan inputs."""

from pathlib import Path
from uuid import UUID

from semflow_research.adapters.codeql.custom import prepare_query, run_query
from semflow_research.adapters.codeql.sarif import parse_sarif
from semflow_research.adapters.codeql.scanner import CodeQLScanner
from semflow_research.domain.errors import AuditError, ExecutionCancelled, ScanPlan
from semflow_research.rules.rules_execution import frozen_supplement_rule
from semflow_research.runtime.scan_inputs import validate_scan
from semflow_research.state.models import Candidate


def check(service, workspace, patched_hash, *, _kernel):
    # Peer: RepairValidationPlan.rescan/static_baseline and repair_rescan.receive.
    # AGENT: preserve the historical rule-level before/after judgment and its
    # limits: absent target rules is not proof of remediation; unknown targets
    # remain needs_review. Failed tools/parsing never become an empty result.
    validate_scan(_kernel, _kernel.spec.inputs.validation_plan.rescan)
    directory, source = service.directory, service.evidence.source_context
    scanner = CodeQLScanner(_kernel=_kernel)
    plan = ScanPlan(source.language, source.query_pack, source.suite)
    output = directory / "patched.sarif"
    _kernel.control.check_active(_kernel.execution_id)
    try:
        if scanner.version() != source.codeql_version:
            raise AuditError("CodeQL 版本与原始冻结扫描不同", code="integrity_error")
        scanner.create_database(
            workspace, directory / "patched-database", directory / "execution.log", plan
        )
        _kernel.control.check_active(_kernel.execution_id)
        scanner.analyze(
            directory / "patched-database", output, directory / "execution.log", plan
        )
    except ExecutionCancelled:
        raise
    except AuditError as exc:
        if exc.code == "integrity_error":
            raise
        return {
            "status": "error",
            "code": "tool_failed",
            "output": str(exc),
            "findings": None,
            "meaning": "Static rescan did not complete; no zero-findings conclusion",
        }
    raw_refs = []
    try:
        raw_refs.append(
            _kernel.artifacts.commit(
                output.read_bytes(), kind="sarif", schema_version="sarif/2.1.0"
            )
        )
        findings = parse_sarif(output, patched_hash)
        for rule_id in source.custom_rule_ids:
            _kernel.control.check_active(_kernel.execution_id)
            rule = frozen_supplement_rule(
                UUID(rule_id),
                source.corpus_scope,
                source.language,
                allow_retired=True,
                _kernel=_kernel,
            )
            pack = directory / "patched-supplements" / rule_id / "pack"
            prepare_query(
                pack, source.language, rule.query, rule.modules, rule.dependencies
            )
            path = pack.parent / "results.sarif"
            findings.extend(
                run_query(
                    directory / "patched-database",
                    pack,
                    path,
                    directory / "execution.log",
                    patched_hash,
                    _kernel=_kernel,
                )
            )
            raw_refs.append(
                _kernel.artifacts.commit(
                    path.read_bytes(), kind="sarif", schema_version="sarif/2.1.0"
                )
            )
    except ExecutionCancelled:
        raise
    except (AuditError, OSError) as exc:
        return {
            "status": "error",
            "code": "parse_failed"
            if getattr(exc, "code", None) == "parse_failed"
            else "tool_failed",
            "output": str(exc),
            "findings": None,
            "sarif_refs": [ref.model_dump(mode="json") for ref in raw_refs],
            "meaning": "Invalid or incomplete static output; no zero-findings conclusion",
        }
    for row in findings:
        for point in [
            *row["locations"],
            *[p for flow in row["code_flows"] for p in flow],
        ]:
            name = point["file"]
            if Path(name).is_absolute():
                try:
                    point["file"] = Path(name).relative_to(workspace).as_posix()
                except ValueError as exc:
                    raise AuditError(
                        "复扫告警不属于修复副本", code="integrity_error"
                    ) from exc
    with _kernel.records.transaction() as records:
        targets = [
            records.get(Candidate, identifier)
            for identifier in service.inputs.candidate_ids
        ]
    selected = {row.static_finding_id for row in targets if row.static_finding_id}
    rules = {row["rule"] for row in source.findings if row["id"] in selected}
    remaining = [row for row in findings if row["rule"] in rules]
    baseline_rules = {row["rule"] for row in source.findings}
    new_alerts = [row for row in findings if row["rule"] not in baseline_rules]
    return {
        "status": "passed"
        if rules and not remaining and not new_alerts
        else "needs_review",
        "findings": findings,
        "remaining_target_rules": sorted({row["rule"] for row in remaining}),
        "new_rule_alerts": new_alerts,
        "codeql_version": source.codeql_version,
        "patched_snapshot_hash": patched_hash,
        "sarif_refs": [ref.model_dump(mode="json") for ref in raw_refs],
        "meaning": "absence of selected rule alerts is not independent proof of remediation",
    }
