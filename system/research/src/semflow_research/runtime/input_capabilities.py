"""Reconstruct nested input artifact permissions from frozen typed bundles only.

Ledger inspection uses immutable bytes, not an algorithm workspace or source
folder. Runtime materialization performs the separate actual evidence checks.
"""

from pydantic import BaseModel
from semflow_contracts.bundles import CandidateBundle, DecisionBundle, EvidenceBundle
from semflow_contracts.common import BundleRef
from semflow_contracts.repair import SuiteRef

from semflow_research.runtime.bundle_reader import read_bundle

SCHEMAS = {
    "targets": CandidateBundle,
    "candidates": CandidateBundle,
    "evidence": EvidenceBundle,
    "decisions": DecisionBundle,
}


def authorize_spec_bundles(store, spec):
    if spec.module == "rules" and spec.operation == "validate":
        from semflow_research.runtime.rule_validation_inputs import origin

        store, _, _ = origin(store, spec.inputs.generation_manifest)
    continuation = getattr(spec.inputs, "continuation", None)
    if continuation is not None:
        from semflow_research.runtime.scout_continuation import read

        store, body, _, _ = read(store, continuation)
        store, _ = read_bundle(
            store, spec.source.snapshot_id, body.candidates, CandidateBundle
        )
        store, _ = read_bundle(
            store, spec.source.snapshot_id, body.evidence, EvidenceBundle
        )

    def visit(value):
        if isinstance(value, BaseModel):
            for name, child in value.__dict__.items():
                if isinstance(child, BundleRef) and name in SCHEMAS:
                    yield child, SCHEMAS[name]
                else:
                    yield from visit(child)
        elif isinstance(value, (tuple, list)):
            for child in value:
                yield from visit(child)

    for reference, schema in visit(spec):
        store, _ = read_bundle(store, spec.source.snapshot_id, reference, schema)

    def suites(value):
        if isinstance(value, SuiteRef):
            yield value
        elif isinstance(value, BaseModel):
            for child in value.__dict__.values():
                yield from suites(child)
        elif isinstance(value, (tuple, list)):
            for child in value:
                yield from suites(child)

    from semflow_research.runtime.suite_inputs import read

    for reference in suites(spec):
        read(reference, store)
    return store
