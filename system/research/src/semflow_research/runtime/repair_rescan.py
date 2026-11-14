"""Receive an immutable original scan for native repair technical validation."""

from pathlib import Path

from semflow_contracts.errors import ResearchError

from semflow_research.adapters.codeql.sarif import parse_sarif
from semflow_research.runtime.baselines import receive as receive_baseline
from semflow_research.runtime.scan_inputs import validate_scan
from semflow_research.state.models import Candidate


def receive(context):
    # WIRE-RECV:research.baseline — peer: research_bridge.repair_baseline.freeze.
    # CLI peer: public.repair_requests.resolved_validation selects the exact
    # published scan inputs. AGENT: review both callers when changing baseline
    # identity, pack/suite selection or failure semantics; never read live defaults.
    # AGENT: retain original database/SARIF, source, tool version and exact scan
    # controls; a selected rule name alone cannot replace its baseline finding.
    plan = context.spec.inputs.validation_plan
    baseline, scan = plan.static_baseline, plan.rescan
    if (
        baseline is None
        or baseline.query_pack != scan.query_pack.name + "@" + scan.query_pack.version
        or baseline.suite != scan.suite.name
        or baseline.supplemental_rules != scan.supplemental_rules
    ):
        raise ResearchError(
            "identity_mismatch", "Repair rescan plan differs from its original baseline"
        )
    validate_scan(context, scan)
    context = receive_baseline(context, baseline)
    try:
        findings = parse_sarif(
            context.baseline_directory / "results.sarif",
            context.spec.source.tree_sha256,
        )
    except Exception as exc:
        raise ResearchError(
            "parse_failed",
            "Original repair baseline SARIF is invalid",
            detail=baseline.sarif,
        ) from exc
    for row in findings:
        for point in [
            *row["locations"],
            *[p for flow in row["code_flows"] for p in flow],
        ]:
            name = point["file"]
            if Path(name).is_absolute():
                try:
                    name = (
                        Path(name).relative_to(baseline.original_source_root).as_posix()
                    )
                except ValueError as exc:
                    raise ResearchError(
                        "evidence_invalid",
                        "Original SARIF location is outside the frozen source",
                    ) from exc
            context.source._slice(name, point["line"], point["end_line"])
            point["file"] = name
    known = {row["id"]: row for row in findings}
    for candidate in context.records.list(Candidate):
        if candidate.static_finding_id is not None:
            finding = known.get(candidate.static_finding_id)
            if finding is None or (
                candidate.location["file"],
                candidate.location["line"],
            ) != (finding["locations"][0]["file"], finding["locations"][0]["line"]):
                raise ResearchError(
                    "identity_mismatch",
                    "Repair target static identity is absent from original SARIF",
                )
    context.source_records.update(context.spec.source.snapshot_id, findings=findings)
    return context
