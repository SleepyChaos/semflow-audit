"""Platform-selected assertions to immutable scientific targets and suite refs."""

from types import SimpleNamespace
from uuid import UUID, uuid5

from semflow_contracts.common import EntityRef
from semflow_research.public.runs import inspect
from semflow_research.public.suites import capture, rebind
from sqlmodel import select

from app.adapters.artifacts import ArtifactStore
from app.research_bridge.models import ResearchBinding
from app.research_bridge.repair_inputs import freeze_targets
from app.research_bridge.requests import research_root


def selected_suite(binding, stage, audit, session, snapshot, targets):
    identifier = UUID(stage.inputs["verification_suite_id"])
    from app.services.verification_suites import read_suite

    original_stage, suite, _ = read_suite(identifier, audit.id)
    existing = session.exec(
        select(ResearchBinding).where(ResearchBinding.stage_id == identifier)
    ).first()
    aliases = []
    current_producer = UUID(targets["candidates"]["artifact"]["owner_execution_id"])
    current_bundle = targets["candidates"]["artifact"]
    if existing:
        receipt = inspect(existing.execution_id, root=research_root())
        reference = receipt.result.suite
        original_ids = existing.entity_map
    else:
        # Import legacy/human assertions as a caller-owned frozen input. Platform
        # review and ownership are checked before freezing; no mutable path enters core.
        from semflow_contracts.modelio.verification import VerificationSuite

        body = suite.model_dump(mode="json")
        required = {i for case in body["cases"] for i in case["candidate_ids"]}
        refs_by_platform = {
            value: EntityRef(
                execution_id=current_producer,
                entity_id=UUID(key.split("/")[1]),
                bundle=current_bundle,
            )
            for key, value in binding.entity_map.items()
            if value in required and key.startswith(str(current_producer) + "/")
        }
        missing = required - refs_by_platform.keys()
        if missing:
            temporary = SimpleNamespace(
                execution_id=binding.execution_id, entity_map=dict(binding.entity_map)
            )
            extra_targets, _ = freeze_targets(
                temporary,
                SimpleNamespace(inputs={"candidate_ids": sorted(missing)}),
                audit,
                session,
                snapshot,
                ArtifactStore().source(str(audit.source_run_id)),
            )
            extra_bundle = extra_targets["candidates"]["artifact"]
            producer = UUID(extra_bundle["owner_execution_id"])
            refs_by_platform.update(
                {
                    value: EntityRef(
                        execution_id=producer,
                        entity_id=UUID(key.split("/")[1]),
                        bundle=extra_bundle,
                    )
                    for key, value in temporary.entity_map.items()
                    if value in missing and key.startswith(str(producer) + "/")
                }
            )
            binding.entity_map = temporary.entity_map
        for case in body["cases"]:
            case["candidate_ids"] = [
                str(refs_by_platform[i].entity_id) for i in case["candidate_ids"]
            ]
        refs = tuple(refs_by_platform[i] for i in sorted(required))
        # Image resolution belongs to the kernel adapter; imported suites must have
        # an already pinned image. UI defaults are resolved by a public helper.
        from semflow_research.public.suites import freeze_image

        reference = capture(
            definition=VerificationSuite.model_validate(body),
            snapshot=snapshot,
            target_refs=refs,
            image_digest=freeze_image(original_stage.result["image"]),
            source="human",
            root=research_root(),
            execution_id=binding.execution_id,
            suite_id=uuid5(binding.execution_id, "suite-input/" + str(identifier)),
        )
        return reference
    from semflow_contracts.repair import SuiteRef

    reference = SuiteRef.model_validate(reference)
    for previous in reference.target_refs:
        platform_id = original_ids.get(f"{previous.execution_id}/{previous.entity_id}")
        matching = next(
            (
                key
                for key, value in binding.entity_map.items()
                if value == platform_id and key.startswith(str(current_producer) + "/")
            ),
            None,
        )
        if matching:
            aliases.append(
                {
                    "previous": previous.model_dump(mode="json"),
                    "current": EntityRef(
                        execution_id=current_producer,
                        entity_id=UUID(matching.split("/")[1]),
                        bundle=current_bundle,
                    ).model_dump(mode="json"),
                }
            )
    inherited = {
        k: v for k, v in original_ids.items() if not k.startswith("execution/")
    }
    binding.entity_map = {**inherited, **binding.entity_map}
    # WIRE-SEND:research.repair_suite — peer: public.suites.rebind / suite_inputs.read.
    # AGENT: only target metadata changes; keep original assertion bytes, provenance
    # and semantic candidate correspondence. Platform IDs never enter kernel cases.
    return rebind(
        reference,
        aliases=aliases,
        root=research_root(),
        execution_id=binding.execution_id,
    )
