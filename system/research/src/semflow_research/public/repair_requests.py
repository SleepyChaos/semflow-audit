"""Local repair input assembly; research identities never require Web entities."""

import hashlib
from pathlib import Path
from uuid import UUID, uuid4

from pydantic import Field
from semflow_contracts.common import Contract
from semflow_contracts.errors import ResearchError
from semflow_contracts.repair import (
    OpenHandsPolicy,
    PatchScope,
    RepairMethodPolicy,
    RepairValidationPlan,
    SuiteBuildResult,
    SuiteRef,
)
from semflow_contracts.runs import (
    ExecutionPolicy,
    Implementation,
    ModelProfile,
    PromptSnapshot,
    RepairGenerateSpec,
    ScanSpec,
)

from semflow_research.public.baselines import for_execution as baseline_for
from semflow_research.public.implementation import code_digest
from semflow_research.public.prompts import freeze_openhands_prompt
from semflow_research.public.runs import inspect, specification
from semflow_research.runtime.artifacts import LocalArtifacts


class RepairOptions(Contract):
    """Only scientific choices/resources; IDs, hashes and Prompts are assembled."""

    method_version: str = Field(default="4", pattern="^[34]$")
    model: ModelProfile
    policy: ExecutionPolicy
    method_policy: RepairMethodPolicy
    validation_plan: RepairValidationPlan
    suite: SuiteRef | None = None
    # Peers: resolved_validation below / repair_rescan.receive / suite_inputs.
    # AGENT: these select published inputs, never current defaults or mutable
    # workspace files; changing this assembly requires reviewing the receivers.
    rescan_from_upstream: bool = False
    suite_execution_id: UUID | None = None


class OpenHandsOptions(RepairOptions):
    worker: OpenHandsPolicy


def resolved_validation(root, upstream_execution_id, options):
    plan, suite = options.validation_plan, options.suite
    if options.suite_execution_id is not None:
        if suite is not None:
            raise ResearchError(
                "invalid_contract", "Select a suite reference or execution, not both"
            )
        published = inspect(options.suite_execution_id, root=root)
        if (
            published is None
            or published.execution_status != "completed"
            or not isinstance(published.result, SuiteBuildResult)
        ):
            raise ResearchError(
                "invalid_contract", "Selected suite execution has no published suite"
            )
        suite = published.result.suite
    if options.rescan_from_upstream:
        if plan.rescan is not None or plan.static_baseline is not None:
            raise ResearchError(
                "invalid_contract",
                "Select upstream rescan or explicit scan references, not both",
            )
        baseline = baseline_for(upstream_execution_id, root=root)
        if baseline is None:
            raise ResearchError(
                "invalid_contract", "Upstream discovery has no frozen static baseline"
            )
        scan = specification(baseline.database.owner_execution_id, root=root)
        upstream = specification(upstream_execution_id, root=root)
        if not isinstance(scan, ScanSpec) or scan.source != upstream.source:
            raise ResearchError(
                "identity_mismatch", "Baseline producer is not the original source scan"
            )
        plan = plan.model_copy(
            update={"rescan": scan.inputs, "static_baseline": baseline}
        )
    return plan, suite


def assemble_openhands(**kwargs) -> RepairGenerateSpec:
    return assemble_repair(engine="openhands", **kwargs)


def assemble_native(**kwargs) -> RepairGenerateSpec:
    return assemble_repair(engine="native", **kwargs)


def assemble_repair(
    *,
    root: Path,
    engine: str,
    upstream_execution_id: UUID,
    candidate_ids: tuple[UUID, ...],
    writable_paths: tuple[str, ...],
    readable_paths: tuple[str, ...],
    max_changed_files: int,
    options: RepairOptions,
    dependency_lock: Path,
    actor: str,
    confirmation_reason: str,
    execution_id: UUID | None = None,
) -> RepairGenerateSpec:
    """Explicit operator confirmation is bound to exact upstream source evidence."""
    if engine not in {"native", "openhands"} or (engine == "openhands") != isinstance(
        options, OpenHandsOptions
    ):
        raise ResearchError("invalid_contract", "Repair engine/options do not match")
    execution_id = execution_id or uuid4()
    from semflow_research.public.targets import select_targets

    source, targets = select_targets(
        root=root,
        upstream_execution_id=upstream_execution_id,
        execution_id=execution_id,
        candidate_ids=candidate_ids,
        actor=actor,
        confirmation_reason=confirmation_reason,
    )
    artifacts = LocalArtifacts(root / "artifacts", execution_id)
    validation_plan, suite = resolved_validation(root, upstream_execution_id, options)
    template = (
        Path(__file__).resolve().parents[1]
        / f"prompts/repair.v{options.method_version}.txt"
    )
    prompt_ref = artifacts.commit(
        template.read_bytes(), kind="prompt", schema_version="prompt/1"
    )
    prompt = PromptSnapshot(
        role="repair",
        template_id="repair",
        version=options.method_version,
        content=prompt_ref,
        sha256=prompt_ref.sha256,
    )
    # WIRE-SEND:research.run — peer: repair_operations.generate / bundle_io.import_targets.
    # AGENT: explicit CLI confirmation binds the selected leaf producer/evidence,
    # never a model assessment or a newly recaptured source snapshot.
    return RepairGenerateSpec(
        execution_id=execution_id,
        module="repair",
        operation="generate",
        lineage={},
        source=source,
        language=source.languages[0],
        implementation=Implementation(
            method_id=f"semflow.repair.{engine}",
            method_version=options.method_version,
            code_digest=code_digest(),
            dependency_lock_digest=hashlib.sha256(
                dependency_lock.read_bytes()
            ).hexdigest(),
        ),
        prompts=(
            prompt,
            *(
                (
                    freeze_openhands_prompt(
                        version=options.worker.prompt_version, artifacts=artifacts
                    ),
                )
                if engine == "openhands"
                else ()
            ),
        ),
        model=options.model,
        policy=options.policy,
        inputs={
            "engine": engine,
            "openhands": options.worker if engine == "openhands" else None,
            "targets": targets,
            "patch_scope": PatchScope(
                writable_paths=writable_paths,
                readable_paths=readable_paths,
                max_changed_files=max_changed_files,
            ),
            "validation_plan": validation_plan,
            "method_policy": options.method_policy,
            "suite": suite,
        },
    )
