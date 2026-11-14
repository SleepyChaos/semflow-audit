"""Retain actual rule tool outputs on waiting, success and failure boundaries."""

from semflow_contracts.common import canonical_bytes
from semflow_contracts.errors import ResearchError
from semflow_contracts.rules import RuleDiagnostics

NAMES = {
    "candidate.json",
    "diagnostic.json",
    "development_feedback.json",
    "project-replay.json",
    "provenance.json",
    "rule-materials.json",
}


def publish(context, *, validation=None, title=None):
    # WIRE-SEND:research.rule_diagnostics — peer: read below / RuleResult.diagnostics and Failure.detail.
    # AGENT: keep raw compile/replay/validation output, including failed attempts;
    # generated fixtures and independent evaluation have different meanings.
    files = {}
    for path in sorted(context.workspace.rglob("*")):
        if (
            path.is_file()
            and not path.is_symlink()
            and (path.suffix in {".sarif", ".log"} or path.name in NAMES)
        ):
            files[path.relative_to(context.workspace).as_posix()] = (
                context.artifacts.commit(
                    path.read_bytes(),
                    kind="sarif"
                    if path.suffix == ".sarif"
                    else "log"
                    if path.suffix == ".log"
                    else "materials",
                    schema_version="semflow.rule-tool-output/1",
                    media_type="application/octet-stream",
                )
            )
    body = RuleDiagnostics(
        execution_id=context.execution_id,
        title=title,
        validation=validation or {},
        files=files,
    )
    return context.artifacts.commit(
        canonical_bytes(body), kind="materials", schema_version=body.schema_version
    ), tuple(files.values())


def read(artifacts, reference, execution_id):
    # WIRE-RECV:research.rule_diagnostics — peer: publish / RuleDiagnostics.
    # AGENT: verify every member before projecting a technical status; a missing
    # or changed log cannot be interpreted as an empty successful check.
    if (
        reference.schema_version != "semflow.rule-diagnostics/1"
        or reference.owner_execution_id != execution_id
    ):
        raise ResearchError("identity_mismatch", "Rule diagnostics identity differs")
    body = RuleDiagnostics.model_validate_json(artifacts.read(reference))
    if body.execution_id != execution_id or any(
        ref.owner_execution_id != execution_id for ref in body.files.values()
    ):
        raise ResearchError(
            "identity_mismatch", "Rule diagnostics contain a foreign producer"
        )
    for ref in body.files.values():
        artifacts.read(ref)
    return body
