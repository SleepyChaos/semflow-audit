"""Algorithm extracted from app.services.rule_preparation_context.

Runtime dependencies are passed explicitly; no platform ORM or configuration.
Changes to JSON require checking the corresponding semflow_contracts/wire peer.
"""

"""Provide retrieved APIs and observed baseline before semantic rule inspection."""
from semflow_research.adapters.codeql.custom import fixed_dependencies
from semflow_research.rules.rule_context import compact_rule_context


def preparation_context(
    service, target, knowledge, evidence=None, materials=(), *, _kernel
):
    files = set(service.inputs.source_paths)
    if target.get("location", {}).get("file"):
        files.add(target["location"]["file"])
    alerts = [
        {
            key: value
            for key, value in finding.items()
            if key in {"id", "rule", "message", "locations", "tags"}
        }
        for finding in service.source_context.findings
        if any(loc.get("file") in files for loc in finding.get("locations", []))
    ]
    windows = source_windows(evidence, materials) if evidence is not None else []
    return {
        "purpose": service.inputs.purpose,
        "source_windows": windows,
        "knowledge": compact_rule_context(
            {"knowledge": knowledge, "semantic_inspection": {}}
        )["knowledge"],
        "dependencies": fixed_dependencies(
            service.source_context.language, _kernel=_kernel
        ),
        "existing_coverage": {
            "query_pack": service.source_context.query_pack,
            "alerts": alerts,
            "total_alerts": len(service.source_context.findings),
        },
        "meaning": "Prepare a detector's codeflow and API inputs, not a business-preserving patch or an automatic vulnerability confirmation. Baseline alerts are observations, not proof of complete coverage. Cite read project evidence for project facts and supplied knowledge IDs for API declarations.",
    }


def source_windows(evidence, materials):
    windows = []
    for row in materials:
        if row["kind"] != "code":
            continue
        reference = row["reference"]
        total = len(evidence.allowed(reference["file"]).read_text().splitlines())
        windows.append(
            {
                "evidence_id": row["id"],
                **reference,
                "total_lines": total,
                "complete_file": reference["start_line"] == 1
                and reference["end_line"] == total,
            }
        )
    return windows
