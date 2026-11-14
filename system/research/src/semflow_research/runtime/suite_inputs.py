"""Validate immutable SuiteRef and materialize it only in the consumer workspace."""

from types import SimpleNamespace
from uuid import UUID

from semflow_contracts.common import canonical_bytes
from semflow_contracts.errors import ResearchError
from semflow_contracts.suites import FrozenSuite

from semflow_research.adapters.snapshot import snapshot_digest
from semflow_research.evidence.context_materials import digest


def read(reference, artifacts, *, depth=0):
    # WIRE-RECV:research.repair_suite — peer: public.suites.capture / suite_build.build.
    # AGENT: verify the whole executable definition and exact image/target/source
    # identity. Never read a producer's mutable tests directory or platform tables.
    if (
        reference.definition.kind != "suite"
        or reference.definition.schema_version != "semflow.repair-suite/1"
    ):
        raise ResearchError("unsupported_version", "Unknown frozen repair suite format")
    body = FrozenSuite.model_validate_json(artifacts.read(reference.definition))
    if (
        reference.suite_hash != reference.definition.sha256
        or reference.suite_id != body.suite_id
        or reference.target_refs != body.target_refs
        or reference.image_digest != body.image_digest
        or reference.source != body.source
    ):
        raise ResearchError(
            "identity_mismatch",
            "SuiteRef differs from its frozen executable definition",
        )
    if depth > 8:
        raise ResearchError("invalid_contract", "Suite derivation is too deep")
    if body.derived_from:
        from semflow_contracts.repair import SuiteRef

        from semflow_research.runtime.bundle_reader import extend_store

        artifacts = extend_store(artifacts, (body.derived_from,))
        original = FrozenSuite.model_validate_json(artifacts.read(body.derived_from))
        original_ref = SuiteRef(
            suite_id=original.suite_id,
            definition=body.derived_from,
            suite_hash=body.derived_from.sha256,
            target_refs=original.target_refs,
            image_digest=original.image_digest,
            source=original.source,
        )
        original = read(original_ref, artifacts, depth=depth + 1)
        aliases = {a.previous.entity_id: a for a in body.target_aliases}
        if len(aliases) != len(body.target_aliases) or any(
            a.previous not in original.target_refs for a in aliases.values()
        ):
            raise ResearchError("identity_mismatch", "Invalid suite target lineage")
        for alias in aliases.values():
            validate_alias(artifacts, body.snapshot_id, alias.previous, alias.current)
        expected = original.model_dump(mode="json")
        expected["target_refs"] = [
            aliases[r.entity_id].current.model_dump(mode="json")
            if r.entity_id in aliases
            else r.model_dump(mode="json")
            for r in original.target_refs
        ]
        for case in expected["definition"]["cases"]:
            case["candidate_ids"] = [
                str(aliases[UUID(i)].current.entity_id) if UUID(i) in aliases else i
                for i in case["candidate_ids"]
            ]
        actual = body.model_dump(mode="json")
        for key in ("derived_from", "target_aliases"):
            expected.pop(key)
            actual.pop(key)
        if actual != expected:
            raise ResearchError(
                "integrity_error",
                "Rebinding changed suite assertions, metadata or source",
            )
    return body


def validate_alias(artifacts, snapshot_id, previous, current):
    from semflow_contracts.bundles import CandidateBundle
    from semflow_contracts.common import BundleRef

    from semflow_research.runtime.bundle_reader import extend_store, read_bundle

    rows = []
    for ref in (previous, current):
        artifacts = extend_store(artifacts, (ref.bundle,))
        artifacts, result = read_bundle(
            artifacts,
            snapshot_id,
            BundleRef(artifact=ref.bundle, entity_ids=(ref.entity_id,)),
            CandidateBundle,
        )
        rows.append(result.records[0])
    # Peer: public.suites.rebind. AGENT: receiving lineage must independently
    # check candidate semantics; producer validation alone cannot authorize aliases.
    if any(
        getattr(rows[0], key) != getattr(rows[1], key)
        for key in ("identity_key", "weakness", "title", "description")
    ) or (
        rows[0].primary_location.model_dump(exclude={"start_column", "end_column"})
        != rows[1].primary_location.model_dump(exclude={"start_column", "end_column"})
    ):
        raise ResearchError(
            "identity_mismatch",
            "Suite target semantics changed; generate new assertions",
        )


def materialize(context, reference):
    body = read(reference, context.artifacts)
    if (
        body.snapshot_id != context.spec.source.snapshot_id
        or body.source_digest != context.spec.source.tree_sha256
        or body.definition.language != context.spec.language
    ):
        raise ResearchError(
            "identity_mismatch", "Repair suite belongs to a different source"
        )
    directory = context.workspace / "suite-inputs" / str(reference.suite_id)
    pointer = directory / "definition.json"
    tests = directory / "tests"
    from semflow_research.adapters.repair.verification_runner import NODE_REPORTER

    files = {**body.definition.files, "pytest.ini": "[pytest]\n"}
    if body.definition.language == "javascript":
        files["verification-reporter.cjs"] = NODE_REPORTER
    if directory.exists():
        if (
            not pointer.is_file()
            or pointer.is_symlink()
            or pointer.read_bytes() != canonical_bytes(body)
        ):
            raise ResearchError(
                "integrity_error", "Suite input view changed or is incomplete"
            )
        observed = {
            p.relative_to(tests).as_posix() for p in tests.rglob("*") if p.is_file()
        }
        if observed != set(files) or any(p.is_symlink() for p in directory.rglob("*")):
            raise ResearchError("integrity_error", "Suite file membership changed")
        if any(
            (tests / name).read_bytes() != content.encode()
            for name, content in files.items()
        ):
            raise ResearchError(
                "integrity_error", "Frozen suite assertion bytes changed"
            )
    else:
        tests.mkdir(parents=True)
        for name, content in files.items():
            if name.endswith(".py"):
                compile(content, name, "exec")
            (tests / name).write_text(content)
        pointer.write_bytes(canonical_bytes(body))
    result = {
        "suite": body.definition.model_dump(mode="json"),
        "image": body.image_digest,
        "snapshot_hash": body.source_digest,
        "candidate_ids": sorted(str(r.entity_id) for r in body.target_refs),
        "origin": body.source,
    }
    # Peers: verification_suites.suite_identity / read_suite. AGENT: this legacy
    # algorithm-view hash is explicit and separate from SuiteRef.suite_hash (bytes).
    result["suite_hash"] = digest(
        {k: result[k] for k in ("suite", "image", "snapshot_hash", "candidate_ids")}
    )
    result["test_files_hash"] = snapshot_digest(tests)
    result["public_definition"] = reference.definition.model_dump(mode="json")
    return (
        SimpleNamespace(
            id=body.suite_id, result=result, inputs={"requirements": body.requirements}
        ),
        body.definition,
        tests,
    )
