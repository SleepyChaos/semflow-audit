"""Translate a frozen public request into explicit scientific algorithm state."""

from dataclasses import replace
from pathlib import Path
from uuid import UUID

from semflow_contracts.common import ArtifactRef, canonical_bytes, digest
from semflow_contracts.errors import ResearchError
from semflow_contracts.modelio.scouting import ScoutRequest
from semflow_contracts.modelio.stages import ReviewRequest
from semflow_contracts.runs import validate_spec

from semflow_research.runtime.algorithm_context import AlgorithmContext
from semflow_research.runtime.artifacts import LocalArtifacts
from semflow_research.runtime.checkpoints import DurableSaver
from semflow_research.runtime.control import LocalControl
from semflow_research.runtime.ledger import LocalLedger, input_artifacts
from semflow_research.runtime.sources import materialize
from semflow_research.state.models import ExecutionRecord, SourceRecord
from semflow_research.state.records import RecordStore


def policy_for(spec, settings):
    # WIRE-RECV:research.run — peer: CLI / platform RunSpec producers.
    # AGENT: every bound below comes from the frozen request, not a platform
    # default. Review the caller/schema when changing limits or method switches.
    policy = spec.policy
    semantic = {
        "context_chars": policy.max_context_chars,
        "repair_context_max_chars": policy.max_context_chars,
        "tool_limit": settings.SEMANTIC_TOOL_LIMIT,
    }
    inputs = spec.inputs
    if spec.module == "repair" and spec.operation == "generate":
        method = inputs.method_policy
        semantic.update(
            context_chars=method.inspection_limits.max_context_chars,
            repair_context_max_chars=method.inspection_limits.max_expanded_context_chars,
            tool_limit=method.inspection_limits.max_steps,
            source_tool_limit=method.inspection_limits.max_steps,
            # Peer: RepairMethodPolicy / InspectionLimits and platform repair_requests.
            # AGENT: preserve the initial reservation and independent call ceiling;
            # do not substitute target count or current tool defaults on resume.
            initial_source_tool_limit=method.inspection_limits.initial_source_steps
            or method.inspection_limits.max_steps,
            repair_call_limit=method.model_call_limit or policy.max_calls or 2**31,
            repair_attempts=method.max_candidates,
            source_budget_version=1,
        )
    result = {
        "model": spec.model.model if spec.model else "",
        "temperature": spec.model.temperature if spec.model else None,
        "timeout": policy.per_call_timeout_seconds,
        "thinking_mode": spec.model.thinking_mode if spec.model else None,
        "budgets": {
            purpose: spec.model.output_tokens if spec.model else 0
            for purpose in ("review", "repair", "rule", "scout", "verification_suite")
        },
        "max_calls": policy.max_calls or 0,
        "max_tokens": policy.max_tokens or 0,
        "max_seconds": policy.max_seconds or 0,
        "execution_mode": policy.mode,
        "max_no_progress": policy.max_no_progress,
        "semantic_policy": semantic,
        "openhands": spec.inputs.openhands.model_dump(mode="json")
        if getattr(spec.inputs, "openhands", None)
        else None,
    }
    if spec.module == "rules" and spec.operation == "generate":
        # Peer: RuleService / rule_materials / rule_context consume this frozen
        # policy. AGENT: map every public switch; never substitute live defaults.
        result["rule_experiment"] = {
            **inputs.generation.model_dump(exclude={"version"}),
            "retrieval_mode": inputs.retrieval.mode,
            "collection_routing": inputs.retrieval.collection_routing,
            "corpus_document_ids": [
                str(i) for i in inputs.retrieval.corpus_document_ids
            ]
            if inputs.retrieval.corpus_document_ids is not None
            else None,
            "execute_dev": True,
        }
    return result


def internal_inputs(spec):
    inputs = spec.inputs
    if spec.module == "discovery" and spec.operation == "scout":
        return ScoutRequest(
            paths=list(inputs.scope_paths),
            inspection_paths=list(inputs.inspection_paths),
            scheduling_profile=inputs.scheduling_profile,
            include_third_party=inputs.include_third_party,
            window_lines=inputs.window_lines,
            max_units=inputs.window_policy.max_windows,
            steps_per_unit=inputs.window_policy.max_steps_per_window,
            max_context_chars=spec.policy.max_context_chars,
        ).model_dump(mode="json")
    if spec.module == "discovery" and spec.operation == "review":
        policy = inputs.policy
        return ReviewRequest(
            paths=list(policy.scope_paths),
            max_steps=policy.max_steps,
            max_context_chars=policy.max_context_chars,
            batch_size=policy.batch_size,
            max_batches=policy.max_batches,
            supplement_insufficient=policy.supplement_insufficient,
            discover=False,
        ).model_dump(mode="json")
    return {}


def assemble(
    spec,
    *,
    root: Path,
    settings,
    model=None,
    budget_owner_id: UUID | None = None,
    upstream=(),
    control_guard=None,
):
    spec = validate_spec(spec)
    if getattr(spec.inputs, "engine", None) == "openhands":
        from semflow_research.adapters.repair.openhands_resources import worker_identity

        identity = worker_identity(settings)
        if (
            settings.OPENHANDS_WORKER_IDENTITY is not None
            and settings.OPENHANDS_WORKER_IDENTITY != identity
        ):
            raise ResearchError(
                "integrity_error",
                "Frozen OpenHands worker identity differs from installed bytes",
            )
        settings = settings.model_copy(update={"OPENHANDS_WORKER_IDENTITY": identity})
    if spec.model is not None and spec.model.output_schema_version != "1":
        raise ResearchError(
            "unsupported_version", "Unknown model output contract version"
        )
    settings = settings.model_copy(
        update={
            "SCAN_TIMEOUT": spec.policy.scan_timeout_seconds
            or spec.policy.tool_timeout_seconds,
            "VALIDATOR_TIMEOUT": spec.policy.tool_timeout_seconds,
            "AI_TIMEOUT": spec.policy.per_call_timeout_seconds,
        }
    )
    ledger = LocalLedger(root)
    ledger.create(spec)
    artifacts = LocalArtifacts(
        ledger.root / "artifacts", spec.execution_id, upstream=input_artifacts(spec)
    )
    workspace = ledger.root / "workspaces" / str(spec.execution_id)
    workspace.mkdir(parents=True, exist_ok=True)
    reader = materialize(
        spec.source,
        artifacts=artifacts,
        execution_id=spec.execution_id,
        target=workspace / "source",
    )
    records = RecordStore(
        ledger.root / "scientific.sqlite3",
        spec.execution_id,
        tuple(upstream),
        read_upstream=False,
    )
    policy = policy_for(spec, settings)
    resource_values = settings.model_dump(mode="json")
    policy["resources"] = resource_values
    if spec.operation == "scout" and spec.inputs.window_policy.max_calls is not None:
        policy["max_calls"] = min(
            policy["max_calls"] or 2**31, spec.inputs.window_policy.max_calls
        )
    record = records.get(ExecutionRecord, spec.execution_id)
    if record is not None:
        # WIRE-RECV:research.resources — peer: snapshot commit below / ToolSettings serialization.
        # AGENT: reject changed non-secret runtime resources; a profile name alone
        # cannot authorize changing tool/model semantics during recovery.
        resource_ref = ArtifactRef.model_validate(record.policy["resources_snapshot"])
        if artifacts.read(resource_ref) != canonical_bytes(resource_values):
            raise ResearchError(
                "integrity_error",
                "Execution resource profile changed; create a new attempt",
            )
    else:
        # WIRE-SEND:research.resources — peer: restart verification above.
        # AGENT: preserve exact profile values while excluding credentials; pair
        # any serialization change with ToolSettings and the receiving byte check.
        resource_ref = artifacts.commit(
            canonical_bytes(resource_values),
            kind="materials",
            schema_version="semflow.tool-resources/1",
        )
    policy["resources_snapshot"] = resource_ref.model_dump(mode="json")
    if record is None:
        records.save(
            ExecutionRecord(
                id=spec.execution_id,
                snapshot_id=spec.source.snapshot_id,
                kind=spec.operation,
                method_version=spec.implementation.method_version,
                inputs=internal_inputs(spec),
                policy=policy,
            )
        )
        records.save(
            SourceRecord(
                id=spec.source.snapshot_id,
                language=spec.language,
                snapshot_hash=spec.source.tree_sha256,
                corpus_scope=spec.source.snapshot_id,
            )
        )
    elif record.policy != policy:
        raise ResearchError(
            "integrity_error",
            "Frozen resource policy differs from the original execution",
        )
    checkpoint = DurableSaver(
        artifacts=artifacts,
        execution_id=spec.execution_id,
        input_digest=digest(spec),
        pointer=workspace / "checkpoint.json",
    )
    context = AlgorithmContext(
        execution_id=spec.execution_id,
        spec=spec,
        root=ledger.root,
        source_root=reader.root,
        workspace=workspace,
        baseline_directory=workspace / "baseline",
        settings=settings,
        artifacts=artifacts,
        executions=ledger,
        records=records,
        source=reader,
        control=LocalControl(
            ledger,
            (budget_owner_id,)
            if budget_owner_id and budget_owner_id != spec.execution_id
            else (),
            guard=control_guard,
        ),
        checkpoints=checkpoint,
        model=model,
        budget_owner_id=budget_owner_id,
        resources_snapshot=resource_ref,
    )
    if model is None and spec.model is not None and spec.operation != "discover":
        from semflow_research.adapters.ai.provider import CompatibleModel

        model = CompatibleModel(_kernel=context)
    return replace(context, model=model)
