"""Discovery adapters and native graph invocation, independent of Web lifecycle."""

from pathlib import Path

from semflow_contracts.common import relative_path
from semflow_contracts.errors import ResearchError

from semflow_research.adapters.codeql.sarif import parse_sarif
from semflow_research.adapters.codeql.scanner import CodeQLScanner
from semflow_research.domain.errors import ScanPlan
from semflow_research.runtime.discovery_outputs import export, export_static
from semflow_research.state.models import Candidate


def scan(context):
    inputs = context.spec.inputs
    from semflow_research.runtime.scan_inputs import validate_scan

    validate_scan(context, inputs)
    scanner = CodeQLScanner(_kernel=context)
    version = scanner.version()
    directory = context.baseline_directory
    directory.mkdir(parents=True, exist_ok=True)
    context.source_records.update(
        context.spec.source.snapshot_id,
        query_pack=inputs.query_pack.name + "@" + inputs.query_pack.version,
        suite=inputs.suite.name,
        codeql_version=version,
        custom_rule_ids=[str(rule.rule_id) for rule in inputs.supplemental_rules],
    )
    plan = ScanPlan(
        context.spec.language,
        inputs.query_pack.name + "@" + inputs.query_pack.version,
        inputs.suite.name,
    )
    context.execution_records.update(
        context.execution_id, phase="create_codeql_database"
    )
    context.control.check_active(context.execution_id)
    scanner.create_database(
        context.source_root, directory / "database", directory / "execution.log", plan
    )
    context.execution_records.update(
        context.execution_id, phase="analyze_codeql_database"
    )
    context.control.check_active(context.execution_id)
    sarif_path = directory / "results.sarif"
    scanner.analyze(
        directory / "database", sarif_path, directory / "execution.log", plan
    )
    from semflow_research.runtime.scan_supplements import apply

    apply(context, inputs.supplemental_rules, directory, sarif_path)
    context.control.check_active(context.execution_id)
    sarif_ref = context.artifacts.commit(
        sarif_path.read_bytes(), kind="sarif", schema_version="sarif/2.1.0"
    )
    try:
        findings = parse_sarif(sarif_path, context.spec.source.tree_sha256)
    except Exception as exc:
        raise ResearchError(
            "parse_failed",
            "CodeQL produced invalid SARIF; raw artifact is retained",
            detail=sarif_ref,
        ) from exc
    for finding in findings:
        for point in [
            *finding["locations"],
            *[point for flow in finding["code_flows"] for point in flow],
        ]:
            name = point["file"]
            if Path(name).is_absolute():
                try:
                    name = Path(name).relative_to(context.source_root).as_posix()
                except ValueError as exc:
                    raise ResearchError(
                        "evidence_invalid",
                        "SARIF location is outside the frozen source root",
                    ) from exc
            relative_path(name)
            point["file"] = name
    context.source_records.update(context.spec.source.snapshot_id, findings=findings)
    static_ref = export_static(context, findings, sarif_ref)
    from semflow_research.evidence.evidence import EvidenceService

    evidence = EvidenceService(
        str(context.spec.source.snapshot_id),
        str(context.execution_id),
        [],
        _kernel=context,
    )
    for finding in findings:
        point = finding["locations"][0]
        source = evidence.read(
            point["file"], point["line"], point.get("end_line", point["line"])
        )
        context.records.save(
            Candidate(
                snapshot_id=context.spec.source.snapshot_id,
                execution_id=context.execution_id,
                origin="static",
                title=finding["rule"],
                description=f"CodeQL {finding['rule']}: {finding['message']}",
                static_finding_id=finding["id"],
                identity_key="static:" + finding["id"],
                novelty="baseline",
                location=point,
                evidence_ids=[source["id"]],
            )
        )
    context.execution_records.update(
        context.execution_id,
        status="completed",
        phase="static_findings_ready",
        result={
            "coverage": {"status": "completed"},
            "static_finding_count": len(findings),
        },
    )
    from semflow_research.runtime.baselines import capture

    return export(context, static_ref=static_ref).model_copy(
        update={"baseline": capture(context, sarif_ref)}
    )


def scout(context):
    continuation = None
    if context.spec.inputs.continuation is not None:
        from semflow_research.runtime.scout_continuation import receive

        context, continuation = receive(context)
    if context.spec.implementation.method_version not in set(map(str, range(1, 9))):
        raise ResearchError(
            "unsupported_version", "Unknown independent scout method version"
        )
    if context.spec.inputs.window_policy.version not in {"1", "2"}:
        raise ResearchError(
            "unsupported_version", "Unknown scout window policy version"
        )
    from semflow_research.discovery.scouting import ScoutService
    from semflow_research.graphs.scouting import build_scout_graph

    service = ScoutService(context.execution_id, context.model, _kernel=context)
    graph = build_scout_graph(service, context.checkpoints)
    graph.invoke(
        {"execution_id": str(context.execution_id)},
        {"configurable": {"thread_id": str(context.execution_id)}},
    )
    output = export(context)
    if continuation is not None:
        from semflow_research.runtime.scout_continuation import merge

        output = merge(context, continuation, output)
    if (
        context.spec.inputs.window_policy.version == "2"
        and output.coverage.status == "none"
    ):
        from semflow_research.discovery.coverage import empty_scout_outcome

        return empty_scout_outcome(context, output)
    return output


def review(context):
    from semflow_research.runtime.bundle_io import import_targets

    if context.spec.inputs.baseline is not None:
        from semflow_research.runtime.baselines import receive

        context = receive(context, context.spec.inputs.baseline)

    previous = context.spec.lineage.retry_of
    continuing = previous is not None and context.spec.inputs.source_execution_ids == (
        previous,
    )
    version = context.spec.inputs.policy.version
    if version not in {"1", "2", "3", "4"} and not (
        version in {"1-no-cache", "2-no-cache", "3-no-cache", "4-no-cache"}
        and continuing
    ):
        raise ResearchError("unsupported_version", "Unknown review policy version")

    context, selected = import_targets(
        context,
        context.spec.inputs.targets,
        context.spec.inputs.evidence,
        source_execution_ids=context.spec.inputs.source_execution_ids,
    )
    if context.spec.implementation.method_version not in set(map(str, range(4, 13))):
        raise ResearchError(
            "unsupported_version",
            "Public review requires an explicit unified review method version",
        )
    from semflow_research.discovery.review import ReviewService
    from semflow_research.graphs.unified_review import build_unified_review_graph

    service = ReviewService(str(context.execution_id), context.model, _kernel=context)
    if continuing:
        from semflow_research.runtime.review_continuation import attach

        attach(context, service, previous, selected)
    graph = build_unified_review_graph(service, context.checkpoints, _kernel=context)
    graph.invoke(
        {"execution_id": str(context.execution_id)},
        {"configurable": {"thread_id": str(context.execution_id)}},
    )
    return export(context)
