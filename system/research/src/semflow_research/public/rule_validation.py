"""Assemble a separate technical recheck from an explicitly approved pending rule."""

from uuid import uuid4

from semflow_contracts.common import EntityRef
from semflow_contracts.errors import ResearchError
from semflow_contracts.results import ResultManifest
from semflow_contracts.rules import RuleValidateInput
from semflow_contracts.runs import RuleValidateSpec

from semflow_research.public.runs import inspect, revision, specification
from semflow_research.runtime.approvals import validate_resume
from semflow_research.runtime.artifacts import LocalArtifacts
from semflow_research.runtime.ledger import input_artifacts


def assemble(command, *, root, execution_id=None):
    waiting = inspect(command.execution_id, root=root)
    generated = specification(command.execution_id, root=root)
    if (
        waiting is None
        or waiting.module != "rules"
        or waiting.operation != "generate"
        or waiting.pending_action is None
        or not command.approval
        or not command.approval.approved
    ):
        raise ResearchError(
            "approval_required",
            "Rule validation needs an explicit approved pending generation",
        )
    artifacts = LocalArtifacts(
        root / "artifacts", command.execution_id, upstream=input_artifacts(waiting)
    )
    validate_resume(
        command,
        waiting,
        revision=revision(command.execution_id, root=root),
        artifacts=artifacts,
        checkpoint=waiting.pending_action.checkpoint,
    )
    manifest = ResultManifest.model_validate_json(artifacts.read(waiting.manifest))
    # WIRE-SEND:research.run — peer: runtime.rule_validation.receive.
    # AGENT: mechanically bind the original pending receipt, approved subjects,
    # holdout and replay. This creates a new technical execution, not a resume or
    # publication; it leaves the original decision/checkpoint unconsumed.
    return RuleValidateSpec(
        execution_id=execution_id or uuid4(),
        module="rules",
        operation="validate",
        lineage={"parent_execution_id": command.execution_id},
        source=generated.source,
        language=generated.language,
        implementation=generated.implementation,
        prompts=(),
        model=None,
        policy=generated.policy,
        inputs=RuleValidateInput(
            generation_manifest=waiting.manifest,
            rule=EntityRef(
                execution_id=command.execution_id,
                entity_id=waiting.result.rule_id,
                bundle=manifest.result,
            ),
            query=waiting.result.rule,
            fixtures=waiting.result.fixtures,
            approval=command.approval,
            holdout=generated.inputs.acceptance.holdout,
            project_replay=waiting.result.project_replay.raw_output
            if waiting.result.project_replay
            else None,
        ),
    )
