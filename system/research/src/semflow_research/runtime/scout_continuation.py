"""Receive only immutable scout outputs, then reuse the native pending-window loop."""

import json

from semflow_contracts.common import canonical_bytes, digest
from semflow_contracts.discovery_trace import DiscoveryTrace
from semflow_contracts.errors import ResearchError
from semflow_contracts.results import ResultEnvelope, ResultManifest
from semflow_contracts.scout_continuation import ScoutContinuation

from semflow_research.runtime.bundle_reader import extend_store
from semflow_research.runtime.ledger import input_artifacts


def read(store, reference):
    # WIRE-RECV:research.scout_continuation — peer: public.scout_continuation.capture.
    # AGENT: verify previous receipt + exact map/bundles before following nested
    # refs. Never read the old workspace or mint new identities for its findings.
    if (
        reference.kind != "materials"
        or reference.schema_version != "semflow.scout-continuation/1"
    ):
        raise ResearchError("unsupported_version", "Unknown scout continuation format")
    body = ScoutContinuation.model_validate_json(store.read(reference))
    store = extend_store(store, input_artifacts(body))
    manifest = ResultManifest.model_validate_json(store.read(body.manifest))
    store = extend_store(store, (manifest.spec, manifest.result))
    previous = ResultEnvelope.model_validate_json(store.read(manifest.result))
    original_spec = json.loads(store.read(manifest.spec))
    from semflow_contracts.runs import validate_spec

    from semflow_research.runtime.factory import internal_inputs

    original_inputs = internal_inputs(validate_spec(original_spec))
    if body.native_inputs.model_dump(mode="json") != original_inputs:
        raise ResearchError(
            "integrity_error",
            "Continuation native inputs differ from the original request",
        )
    if (
        previous.implementation.code_digest != body.code_digest
        or previous.implementation.dependency_lock_digest != body.dependency_lock_digest
    ):
        raise ResearchError(
            "identity_mismatch", "Continuation implementation identity changed"
        )
    if (
        manifest.execution_id != body.previous_execution_id
        or previous.execution_id != body.previous_execution_id
        or previous.operation != "scout"
        or previous.result is None
        or previous.execution_status not in {"completed", "failed", "cancelled"}
    ):
        raise ResearchError(
            "identity_mismatch", "Continuation refers to a different scout execution"
        )
    if (
        manifest.input_digest != previous.input_digest
        or digest(original_spec) != previous.input_digest
        or original_spec["source"]["snapshot_id"] != str(body.snapshot_id)
        or original_spec["source"]["tree_sha256"] != body.source_digest
        or previous.implementation.method_version != body.method_version
    ):
        raise ResearchError(
            "integrity_error",
            "Continuation source or implementation differs from the original receipt",
        )
    output = previous.result
    if (
        output.project_map,
        output.analysis_trace,
        output.candidates,
        output.evidence,
    ) != (body.project_map, body.trace, body.candidates, body.evidence):
        raise ResearchError(
            "integrity_error", "Continuation inputs differ from published scout outputs"
        )
    trace = DiscoveryTrace.model_validate_json(store.read(body.trace))
    project = json.loads(store.read(body.project_map))
    if (
        trace.execution_id != body.previous_execution_id
        or trace.snapshot_id != body.snapshot_id
        or trace.source_digest != body.source_digest
        or project.get("snapshot") != body.source_digest
    ):
        raise ResearchError(
            "identity_mismatch", "Continuation map/trace belongs to another source"
        )
    return store, body, trace, project


def receive(context):
    from dataclasses import replace

    from semflow_research.runtime.bundle_io import import_targets
    from semflow_research.runtime.factory import internal_inputs

    store, body, trace, project = read(
        context.artifacts, context.spec.inputs.continuation
    )
    if (body.snapshot_id, body.source_digest, body.method_version) != (
        context.spec.source.snapshot_id,
        context.spec.source.tree_sha256,
        context.spec.implementation.method_version,
    ):
        raise ResearchError(
            "identity_mismatch", "Continuation method/source differs from this request"
        )
    if (body.code_digest, body.dependency_lock_digest) != (
        context.spec.implementation.code_digest,
        context.spec.implementation.dependency_lock_digest,
    ):
        raise ResearchError(
            "identity_mismatch",
            "Continuation requires its original algorithm and dependency identity",
        )
    native = internal_inputs(context.spec)
    original = body.native_inputs.model_dump(mode="json")
    if {k: v for k, v in native.items() if k != "continuation_from_id"} != {
        k: v for k, v in original.items() if k != "continuation_from_id"
    }:
        raise ResearchError(
            "invalid_contract",
            "Continuation cannot change frozen map scheduling, scope or window policy",
        )
    context = replace(context, artifacts=store)
    context, _ = import_targets(context, body.candidates, body.evidence)
    completed = [
        row for row in trace.state.get("units", []) if row["status"] == "inspected"
    ]
    known = {row["id"] for row in project["units"]}
    if any(row["unit_id"] not in known for row in completed):
        raise ResearchError(
            "integrity_error",
            "Inherited completed window is absent from the frozen map",
        )
    native["continuation_from_id"] = str(body.previous_execution_id)
    (context.workspace / "scout-map.json").write_bytes(canonical_bytes(project))
    context.execution_records.update(
        context.execution_id,
        inputs=native,
        result={
            "units": completed,
            "source_execution_ids": list(
                dict.fromkeys(
                    [
                        *trace.state.get("source_execution_ids", []),
                        str(body.previous_execution_id),
                    ]
                )
            ),
            "snapshot_hash": body.source_digest,
            "continuation": {
                "from_execution_id": str(body.previous_execution_id),
                "inherited_windows": len(completed),
                "inherited_unit_ids": [row["unit_id"] for row in completed],
            },
        },
    )
    return context, body


def merge(context, body, output):
    from semflow_research.runtime.discovery_merge import index

    return output.model_copy(
        update={
            "candidates": index(
                context, "candidate", (body.candidates, output.candidates)
            ),
            "evidence": index(context, "evidence", (body.evidence, output.evidence)),
        }
    )
