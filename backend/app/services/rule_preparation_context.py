"""Provide retrieved APIs and observed baseline before semantic rule inspection."""

from app.adapters.codeql.custom import fixed_dependencies
from app.services.rule_context import compact_rule_context


def preparation_context(service, target, knowledge, evidence=None, materials=()):
    files = set(service.inputs.source_paths)
    if target.get("location", {}).get("file"):
        files.add(target["location"]["file"])
    alerts = [
        {
            key: value
            for key, value in finding.items()
            if key in {"id", "rule", "message", "locations", "tags"}
        }
        for finding in service.audit.findings
        if any(loc.get("file") in files for loc in finding.get("locations", []))
    ]
    windows = source_windows(evidence, materials) if evidence is not None else []
    return {
        "purpose": service.inputs.purpose,
        "source_windows": windows,
        "knowledge": compact_rule_context(
            {"knowledge": knowledge, "semantic_inspection": {}}
        )["knowledge"],
        "dependencies": fixed_dependencies(service.audit.language),
        "existing_coverage": {
            "query_pack": service.audit.query_pack,
            "alerts": alerts,
            "total_alerts": len(service.audit.findings),
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
