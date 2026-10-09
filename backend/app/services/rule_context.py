"""A lossless code/knowledge view; full provenance stays in immutable artifacts."""

import json

from app.adapters.codeql.custom import fixed_dependencies
from app.services.context_materials import digest


def compact_rule_context(context):
    result = dict(context)
    result["knowledge"] = [
        {
            **{
                k: row[k]
                for k in (
                    "id",
                    "title",
                    "source",
                    "corpus",
                    "language",
                    "content",
                    "retrieval_slot",
                    "version",
                )
                if k in row
            },
            "provenance": {
                k: value
                for k, value in row.get("provenance", {}).items()
                if k
                in {
                    "api_version",
                    "cwe",
                    "cwe_ids",
                    "license",
                    "commit",
                    "source_sha256",
                    "query_pack",
                    "library_pack",
                }
            },
            "validation": {
                k: value
                for k, value in row.get("provenance", {}).get("validation", {}).items()
                if k in {"status", "kind"}
            }
            if isinstance(row.get("provenance", {}).get("validation"), dict)
            else "API reference",
            "artifact_record_digest": digest(row),
        }
        for row in context["knowledge"]
    ]
    inspection = dict(context["semantic_inspection"])
    # Evidence bodies and facts are kept exactly once, including unknowns and citations.
    inspection.pop("inventory", None)
    result["semantic_inspection"] = inspection
    result["materials_note"] = (
        "Complete evidence/knowledge content is retained. Expanded provenance, dependency lock and verification logs are in rule-materials.json. IDs and hashes bind this model view to that artifact."
    )
    return result


def build_rule_context(synthesis, state):
    s = synthesis.service
    if s.stage.prompt_version in {"6", "7", "8"}:
        from app.services.rule_materials import load_rule_materials

        bundle = load_rule_materials(s, state)
        state = {
            **state,
            "knowledge": bundle["knowledge"],
            "target": bundle["target"],
        }
    context = {
        "requirement": s.inputs.requirement,
        "strategy": s.inputs.strategy,
        "purpose": s.inputs.purpose,
        "language": s.audit.language,
        "knowledge": state["knowledge"],
        "confirmed_target": state.get("target"),
        "existing_coverage": {
            "baseline": s.audit.query_pack,
            "alerts": s.audit.findings,
            "published_versions": s.audit.custom_rule_ids,
        },
        "dependencies": fixed_dependencies(s.audit.language),
        "compiler_feedback": None,
    }
    if s.stage.prompt_version in {"6", "7", "8"}:
        context["phase"] = "generate_rule"
        context["output_contract"] = {
            "purpose": s.inputs.purpose,
            "strategies": ["new_query", "extend", "model"],
            "namespace": "audit/ or custom/ (server may assign metadata ID)",
            "knowledge_ids": [row["id"] for row in state["knowledge"]],
        }
        context["semantic_inspection"] = {
            k: v for k, v in bundle["inspection"].items() if k != "inventory"
        }
        target_files = {bundle["target"].get("location", {}).get("file")}
        if s.stage.prompt_version in {"7", "8"} and not bundle["target"].get(
            "candidate_id"
        ):
            target_files = set(s.inputs.source_paths)
        context["existing_coverage"]["alerts"] = [
            f
            for f in s.audit.findings
            if any(loc.get("file") in target_files for loc in f.get("locations", []))
        ]
        context["existing_coverage"]["total_alerts"] = len(s.audit.findings)
        if s.stage.prompt_version == "8":
            context["source_windows"] = bundle["preparation_context"]["source_windows"]
            context["existing_coverage"] = {
                **bundle["preparation_context"]["existing_coverage"],
                "published_versions": s.audit.custom_rule_ids,
            }
    full = s.stage.prompt_version in {
        "3",
        "4",
        "5",
        "6",
        "7",
        "8",
    } and s.experiment.get("full_feedback", True)
    if full:
        context["previous_candidate"] = None
    if state.get("attempt", 0):
        previous = synthesis._pack(state)
        diagnostic = json.loads((previous / "diagnostic.json").read_text())
        context["compiler_feedback"] = (
            diagnostic
            if full
            else (diagnostic["message"] + "\n" + diagnostic["log_tail"][-5000:])
        )
        if full:
            context["previous_candidate"] = synthesis._load(state).model_dump(
                mode="json"
            )
        for name in ("development_feedback", "type_feedback"):
            path = previous / f"{name}.json"
            if path.exists():
                context[name] = json.loads(path.read_text())
        replay = previous / "project-replay.json"
        if replay.exists():
            context["project_feedback"] = json.loads(replay.read_text())
    if s.stage.prompt_version in {"7", "8"} and s.experiment.get(
        "compact_context", True
    ):
        context = compact_rule_context(context)
    if (
        s.stage.prompt_version == "8"
        and state.get("attempt", 0)
        and s.experiment.get("compact_context", True)
    ):
        from app.services.rule_feedback import compact_feedback

        context = compact_feedback(context, str(previous.relative_to(s.directory)))
    return context
