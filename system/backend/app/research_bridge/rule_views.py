"""Explicit conversion from research replay identities to legacy platform views."""

from uuid import UUID

from app.adapters.artifacts import ArtifactStore
from app.persistence.stage_models import Candidate
from app.services.context_materials import digest


def project_replay(session, stage, audit, raw):
    # Peer: rule_project_validation.replay_project -> old confirm/publish routes.
    # AGENT: retain the scientific identity. Legacy snapshot/input/target hashes
    # are verified conversions of frozen platform facts, never hex substitutions.
    target = (
        session.get(Candidate, UUID(stage.inputs["candidate_id"]))
        if stage.inputs.get("candidate_id")
        else None
    )
    metadata = ArtifactStore().directory(str(audit.id)) / "database/codeql-database.yml"
    original = stage.result["research_platform_baseline"]
    identity = {
        **raw["identity"],
        "audit": str(audit.id),
        "snapshot": original["snapshot"],
        "input_hash": digest(stage.inputs),
        "target_hash": digest(target.model_dump(mode="json")) if target else None,
        "baseline_hash": original["findings"],
        "custom_rules": original["custom_rules"],
        "database_metadata_hash": digest(metadata.read_text()),
    }
    # Peer: services.rule_project_validation.confirm_project_match.
    # AGENT: matched_ids/findings[].id remain opaque scientific SARIF identities,
    # not Candidate/RuleVersion UUIDs; the confirmation receiver selects the exact
    # saved replay row. Only the verified platform identity hashes above convert.
    return {**raw, "identity": identity, "research_identity": raw["identity"]}
