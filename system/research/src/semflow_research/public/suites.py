"""Caller-owned suite freezing and typed presentation; no Web or ORM dependency."""

from semflow_contracts.common import canonical_bytes
from semflow_contracts.repair import SuiteRef
from semflow_contracts.suites import FrozenSuite

from semflow_research.runtime.artifacts import LocalArtifacts


def capture(
    *,
    definition,
    snapshot,
    target_refs,
    image_digest,
    source,
    root,
    execution_id,
    suite_id,
    requirements="",
):
    body = FrozenSuite(
        suite_id=suite_id,
        snapshot_id=snapshot.snapshot_id,
        source_digest=snapshot.tree_sha256,
        definition=definition,
        target_refs=target_refs,
        source=source,
        image_digest=image_digest,
        requirements=requirements,
    )
    # WIRE-SEND:research.repair_suite — peer: runtime.suite_inputs.read.
    # AGENT: capture assertions verbatim with image and source/target identities;
    # caller ownership/approval is separate and may not be inferred by the receiver.
    return commit(body, root=root, execution_id=execution_id)


def commit(body, *, root, execution_id):
    body = FrozenSuite.model_validate(body.model_dump(mode="json"))
    ref = LocalArtifacts(root / "artifacts", execution_id).commit(
        canonical_bytes(body), kind="suite", schema_version=body.schema_version
    )
    return SuiteRef(
        suite_id=body.suite_id,
        definition=ref,
        suite_hash=ref.sha256,
        target_refs=body.target_refs,
        source=body.source,
        image_digest=body.image_digest,
    )


def read(reference, *, root):
    from semflow_research.runtime.suite_inputs import read as receive

    return receive(
        reference,
        LocalArtifacts(root / "artifacts", reference.definition.owner_execution_id),
    )


def rebind(reference, *, aliases, root, execution_id):
    """Map caller identities while preserving assertion bytes and full provenance."""
    from semflow_contracts.errors import ResearchError
    from semflow_contracts.suites import SuiteTargetAlias

    from semflow_research.runtime.suite_inputs import validate_alias

    original = read(reference, root=root)
    aliases = tuple(SuiteTargetAlias.model_validate(a) for a in aliases)
    mapping = {}
    store = LocalArtifacts(root / "artifacts", execution_id)
    for alias in aliases:
        if (
            alias.previous not in original.target_refs
            or alias.previous.entity_id in mapping
        ):
            raise ResearchError(
                "identity_mismatch", "Suite target alias is missing or duplicated"
            )
        validate_alias(store, original.snapshot_id, alias.previous, alias.current)
        mapping[alias.previous.entity_id] = alias.current
    definition = original.definition.model_copy(
        update={
            "cases": [
                case.model_copy(
                    update={
                        "candidate_ids": [
                            mapping[i].entity_id if i in mapping else i
                            for i in case.candidate_ids
                        ]
                    }
                )
                for case in original.definition.cases
            ]
        }
    )
    body = original.model_copy(
        update={
            "definition": definition,
            "target_refs": tuple(
                mapping.get(r.entity_id, r) for r in original.target_refs
            ),
            "derived_from": reference.definition,
            "target_aliases": aliases,
        }
    )
    return commit(body, root=root, execution_id=execution_id)


def freeze_image(image):
    """Resolve a caller-selected image to the immutable identity used by core tests."""
    from semflow_research.adapters.repair.verification_runner import resolve_image

    return resolve_image(image)


def reporter_bytes():
    from semflow_research.adapters.repair.verification_runner import NODE_REPORTER

    return NODE_REPORTER.encode()
