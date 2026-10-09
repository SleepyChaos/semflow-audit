"""Focused retry observations with immutable full diagnostic references."""

import re

from app.services.context_materials import digest


def diagnostic_view(diagnostic, artifact):
    lines = diagnostic.get("log_tail", "").splitlines()
    matches = {
        i
        for i, line in enumerate(lines)
        if re.search(
            r"\b(?:ERROR|WARNING|FATAL|Exception|Could not|Cannot resolve|SyntaxError|TypeError)\b",
            line,
            re.I,
        )
    }
    # Keep complete matching lines and adjacent context. Never truncate QL/source.
    selected = {
        j for i in matches for j in range(max(0, i - 1), min(len(lines), i + 2))
    }
    return {
        "message": diagnostic["message"],
        "code": diagnostic.get("code"),
        "log_tail": "\n".join(line for i, line in enumerate(lines) if i in selected)
        if matches
        else diagnostic.get("log_tail", ""),
        "artifact": artifact,
        "artifact_digest": digest(diagnostic),
        "note": "All matched error/warning lines and adjacent context retained. Full diagnostic remains in artifact; unmatched logs are kept whole when no error pattern is found.",
    }


def compact_feedback(context, previous_pack):
    result = dict(context)
    if isinstance(context.get("compiler_feedback"), dict):
        result["compiler_feedback"] = diagnostic_view(
            context["compiler_feedback"], f"{previous_pack}/diagnostic.json"
        )
    development = context.get("development_feedback")
    if development:
        result["development_feedback"] = {
            **{k: v for k, v in development.items() if k != "tests"},
            "tests": {
                kind: {k: v for k, v in check.items() if k != "findings"}
                for kind, check in development["tests"].items()
            },
            "artifact": f"{previous_pack}/development_feedback.json",
            "artifact_digest": digest(development),
            "note": "Exact expected/actual root locations and statuses are kept; full SARIF paths remain in artifact. Candidate fixture bodies are retained in previous_candidate.",
        }
    project = context.get("project_feedback")
    if project:
        result["project_feedback"] = {
            **{k: v for k, v in project.items() if k not in {"findings", "identity"}},
            "findings": [
                {
                    "id": f["id"],
                    "rule": f.get("rule"),
                    "message": f.get("message"),
                    "locations": f["locations"],
                    "tags": f.get("tags", []),
                }
                for f in project.get("findings", [])
            ],
            "artifact": f"{previous_pack}/project-replay.json",
            "artifact_digest": digest(project),
        }
    return result
