"""Read a portable immutable generation approval, without its mutable workspace."""

import json

from semflow_contracts.common import digest
from semflow_contracts.errors import ResearchError
from semflow_contracts.results import ResultEnvelope, ResultManifest
from semflow_contracts.rules import RuleDiagnostics
from semflow_contracts.runs import validate_spec

from semflow_research.runtime.bundle_reader import extend_store
from semflow_research.runtime.ledger import input_artifacts


def origin(store, reference):
    if reference is None or reference.kind != "result_manifest":
        raise ResearchError(
            "invalid_contract", "Rule validation needs its generation manifest"
        )
    manifest = ResultManifest.model_validate_json(store.read(reference))
    if manifest.execution_id != reference.owner_execution_id:
        raise ResearchError("identity_mismatch", "Generation manifest producer differs")
    store = extend_store(store, (manifest.spec, manifest.result))
    spec = validate_spec(json.loads(store.read(manifest.spec)))
    envelope = ResultEnvelope.model_validate_json(store.read(manifest.result))
    if (
        spec.module != "rules"
        or spec.operation != "generate"
        or spec.execution_id != manifest.execution_id
        or envelope.execution_id != manifest.execution_id
        or envelope.input_digest != digest(spec)
        or manifest.input_digest != digest(spec)
        or envelope.implementation != spec.implementation
        or envelope.module != "rules"
        or envelope.operation != "generate"
        or envelope.execution_status != "awaiting_input"
        or envelope.result is None
        or envelope.pending_action is None
        or envelope.manifest is not None
    ):
        raise ResearchError(
            "identity_mismatch", "Expected the exact pending generation receipt"
        )
    store = extend_store(store, (*input_artifacts(spec), *input_artifacts(envelope)))
    for ref in input_artifacts(envelope):
        store.read(ref)
    if envelope.result.diagnostics:
        diagnostic = RuleDiagnostics.model_validate_json(
            store.read(envelope.result.diagnostics)
        )
        if diagnostic.execution_id != envelope.execution_id:
            raise ResearchError(
                "identity_mismatch", "Generation diagnostics producer differs"
            )
        store = extend_store(store, tuple(diagnostic.files.values()))
    return store, spec, envelope.model_copy(update={"manifest": reference})
