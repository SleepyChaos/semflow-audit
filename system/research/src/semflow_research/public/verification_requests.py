"""Assemble suite/comparison requests from published scientific executions."""

import hashlib
from pathlib import Path
from uuid import UUID, uuid4

from semflow_contracts.common import Contract, EntityRef
from semflow_contracts.errors import ResearchError
from semflow_contracts.repair import (
    RepairResult,
    RepairValidationPlan,
    SuiteBuildResult,
    TestPlan,
)
from semflow_contracts.runs import (
    ExecutionPolicy,
    Implementation,
    ModelProfile,
    PromptSnapshot,
    RepairGenerateSpec,
    RepairVerifySpec,
    SuiteBuildSpec,
)

from semflow_research.public.implementation import code_digest
from semflow_research.public.runs import inspect, specification
from semflow_research.public.targets import select_targets
from semflow_research.runtime.artifacts import LocalArtifacts


class SuiteOptions(Contract):
    model: ModelProfile
    policy: ExecutionPolicy


class VerifyOptions(Contract):
    policy: ExecutionPolicy
    syntax: bool = False
    project_tests: bool = False
    rescan: bool = False


def _implementation(method, version, dependency_lock):
    return Implementation(
        method_id=method,
        method_version=version,
        code_digest=code_digest(),
        dependency_lock_digest=hashlib.sha256(dependency_lock.read_bytes()).hexdigest(),
    )


def assemble_suite(
    *,
    root: Path,
    upstream_execution_id: UUID,
    candidate_ids: tuple[UUID, ...],
    options: SuiteOptions,
    dependency_lock: Path,
    actor: str,
    confirmation_reason: str,
    requirements: str,
    execution_id: UUID | None = None,
) -> SuiteBuildSpec:
    execution_id = execution_id or uuid4()
    source, targets = select_targets(
        root=root,
        upstream_execution_id=upstream_execution_id,
        execution_id=execution_id,
        candidate_ids=candidate_ids,
        actor=actor,
        confirmation_reason=confirmation_reason,
    )
    artifacts = LocalArtifacts(root / "artifacts", execution_id)
    template = Path(__file__).resolve().parents[1] / "prompts/verification_suite.v2.txt"
    prompt = artifacts.commit(
        template.read_bytes(), kind="prompt", schema_version="prompt/1"
    )
    # Interface peer: runtime.suite_build.build. AGENT: requirements are exact
    # UTF-8 text, not JSON; review both ends before changing encoding or defaults.
    behavior = artifacts.commit(
        requirements.encode("utf-8"),
        kind="materials",
        schema_version="semflow.requested-behavior/1",
        media_type="text/plain",
    )
    return SuiteBuildSpec(
        execution_id=execution_id,
        module="repair",
        operation="build_suite",
        lineage={},
        source=source,
        language=source.languages[0],
        implementation=_implementation("semflow.repair.suite", "2", dependency_lock),
        prompts=(
            PromptSnapshot(
                role="verification_suite",
                template_id="verification_suite",
                version="2",
                content=prompt,
                sha256=prompt.sha256,
            ),
        ),
        model=options.model,
        policy=options.policy,
        inputs={
            "targets": targets,
            "requested_behavior": behavior,
            "runtime_profile": options.policy.resource_profile,
        },
    )


def assemble_verify(
    *,
    root: Path,
    repair_execution_id: UUID,
    suite_execution_id: UUID,
    options: VerifyOptions,
    dependency_lock: Path,
    execution_id: UUID | None = None,
) -> RepairVerifySpec:
    repair = inspect(repair_execution_id, root=root)
    suite = inspect(suite_execution_id, root=root)
    original = specification(repair_execution_id, root=root)
    suite_spec = specification(suite_execution_id, root=root)
    if (
        repair is None
        or suite is None
        or repair.execution_status != "completed"
        or suite.execution_status != "completed"
        or not isinstance(original, RepairGenerateSpec)
        or not isinstance(repair.result, RepairResult)
        or not isinstance(suite.result, SuiteBuildResult)
        or repair.result.patch is None
        or repair.result.patched_source is None
        or original.source != suite_spec.source
    ):
        raise ResearchError(
            "identity_mismatch",
            "Comparison needs a published patch and suite for the same source",
        )
    if options.rescan and original.inputs.validation_plan.rescan is None:
        raise ResearchError(
            "invalid_contract", "Requested rescan has no frozen repair baseline"
        )
    # WIRE-SEND:research.run — peer: runtime.repair_verify.receive.
    # AGENT: copy exact published patch/source/suite and leaf target identities;
    # never recapture a mutable workspace or infer acceptance from a passed test.
    return RepairVerifySpec(
        execution_id=execution_id or uuid4(),
        module="repair",
        operation="verify",
        lineage={},
        source=original.source,
        language=original.language,
        implementation=_implementation("semflow.repair.verify", "1", dependency_lock),
        prompts=(),
        model=None,
        policy=options.policy,
        inputs={
            "repair": EntityRef(
                execution_id=repair_execution_id,
                entity_id=repair.result.repair_id,
                bundle=repair.manifest,
            ),
            "patch": repair.result.patch,
            "patched_source": repair.result.patched_source,
            "suite": suite.result.suite,
            "validation_plan": RepairValidationPlan(
                syntax=options.syntax,
                project_tests=TestPlan(
                    runner="python_pytest"
                    if original.language == "python"
                    else "javascript_test",
                    resource_profile=options.policy.resource_profile,
                )
                if options.project_tests
                else None,
                rescan=original.inputs.validation_plan.rescan
                if options.rescan
                else None,
                static_baseline=original.inputs.validation_plan.static_baseline
                if options.rescan
                else None,
                before_after=True,
            ),
        },
    )
