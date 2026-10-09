"""Conditional, sourced library semantics; these never substitute for code evidence."""

import ast
import json

FLASK_SOURCE = "https://flask.palletsprojects.com/en/stable/api/"


def framework_facts(context):
    imports = set()
    for row in context["evidence"]:
        if row["kind"] != "code" or not row["reference"].get("file", "").endswith(
            ".py"
        ):
            continue
        try:
            tree = ast.parse(row["content"])
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.add(node.module or "")
    facts = []
    if "flask" in imports:
        facts.append(
            {
                "library": "Flask",
                "documentation_version": "3.1.x",
                "project_version": "unverified unless dependency evidence establishes it",
                "source": FLASK_SOURCE,
                "facts": [
                    "With Flask default response_class, a view returning str becomes a response body, and Response.default_mimetype is text/html. A plain Python string is not automatically text/plain or HTML-escaped.",
                    "make_response wrapping a string does not sanitize it. jsonify uses JSON response semantics; explicit mimetype/Content-Type, custom response_class, after_request and other response transformations must be checked.",
                    "render_template enables autoescaping for configured HTML template extensions by default; escaping depends on actual template context, Markup/safe, custom configuration and renderer.",
                    "send_from_directory uses safe_join to contain the filename under a trusted directory. A request-derived filename alone is not proof of traversal; an attacker-controlled directory argument requires separate analysis.",
                ],
                "limit": "Conditional library defaults, not project facts or vulnerability labels. Verify actual bound API, version/configuration and local wrappers. Do not invent dependencies or ignore overriding code. Source/control gaps remain unknown.",
            }
        )
    return facts


def enrich_semantic_context(
    context, max_context_chars=40000, *, include_value_clues=False
):
    enriched = {
        **context,
        "semantic_context_version": 2,
        **(
            {
                "inspection_tasks": [
                    {
                        **t,
                        "instruction": t["instruction"]
                        + (
                            " Inspect cryptographic hashes, password/token randomness and cookie security attributes in their actual purpose; distinguish security-sensitive uses from benign checksums/simulation."
                            if t["id"] == "secrets_config"
                            else " Trace untrusted request values into trusted server-side session/state and actual security transitions, not only HTTP method/CSRF."
                            if t["id"] == "state_integrity"
                            else ""
                        ),
                    }
                    for t in context["inspection_tasks"]
                ]
            }
            if "inspection_tasks" in context
            else {}
        ),
        "framework_semantics": framework_facts(context),
        "policy_proof_boundary": {
            "requirement": "Missing authentication/authorization/rate limiting/logging is not by itself a vulnerability. Establish why this specific operation requires that control from actual confidentiality/role/ownership/business-contract evidence. Route names, HTTP verbs and detector claims alone do not establish policy.",
            "missing_policy": "Keep a conditional hypothesis with an explicit missing policy prerequisite, or mark not applicable if code shows a deliberately public harmless operation. Do not invent an access policy for every public handler.",
            "distinction": "A required policy and an observed guard are separate premises; direct injection does not automatically prove a second missing-authentication condition.",
        },
        "path_proof_boundary": "Follow the actual value reaching the operation across assignments, overwritten values, constant branches, slicing/container access and supplied helper bodies. Source occurrence does not prove taint reaches the sink. Summaries and earlier candidate claims must agree with the final path evidence; contradictions require resolving the path or remaining insufficient.",
    }

    if not include_value_clues:
        return enriched

    from app.adapters.constant_evidence import evidence_clues

    clues = evidence_clues(context["evidence"])
    selected = []
    cap = max(
        0,
        min(
            3000,
            max_context_chars - len(json.dumps(enriched, ensure_ascii=False)) - 6000,
        ),
    )
    for clue in clues:
        if len(json.dumps([*selected, clue], ensure_ascii=False)) > cap:
            break
        selected.append(clue)
    return {
        **enriched,
        "static_value_clues": selected,
        "static_value_clue_limit": {
            "engine": "astroid 4.3.3, closed literal expressions only, no target imports/calls",
            "omitted_clues": len(clues) - len(selected),
            "meaning": "Read the cited actual source and evaluate the associated branch/selector and final value path. These are bounded static inference clues, not executed tests, whole-function taint proofs or safe/unsafe verdicts. Unknown mutations/overrides/unsupported expressions must remain unknown.",
        },
    }
