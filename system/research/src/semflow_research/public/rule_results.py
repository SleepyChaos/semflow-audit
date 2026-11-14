"""Verified rule outputs for platform DTO conversion and local inspection."""

import json
from dataclasses import dataclass
from pathlib import Path

from semflow_contracts.errors import ResearchError
from semflow_contracts.results import ResultManifest

from semflow_research.runtime.ledger import LocalLedger
from semflow_research.runtime.rule_diagnostics import read
from semflow_research.runtime.rule_inputs import read_rule


@dataclass(frozen=True)
class RuleProjection:
    title: str
    query: str
    modules: dict
    dependencies: dict
    fixtures: dict
    retrieval: list
    validation: dict
    previous_manifest: object | None


def read_projection(envelope, *, root: Path) -> RuleProjection:
    # WIRE-RECV:research.rule_diagnostics — peer: rule_outputs.export / RuleDiagnostics.
    # AGENT: only exact published bytes can be projected. Independent checks,
    # generated-fixture approval and platform publication are separate facts.
    ledger = LocalLedger(root)
    saved = ledger.inspect(envelope.execution_id)
    if saved != envelope or saved.result is None or saved.module != "rules":
        raise ResearchError(
            "integrity_error", "Only an exact published rule result can be projected"
        )
    with ledger._connect() as db:
        artifacts = ledger._store(ledger._row(db, saved.execution_id))
    result = saved.result
    if result.diagnostics is None:
        raise ResearchError(
            "invalid_contract",
            "Rule projection requires its original method diagnostics",
        )
    diagnostic = read(artifacts, result.diagnostics, saved.execution_id)
    query, modules, dependencies = read_rule(
        result.rule, artifacts, result.rule.language
    )
    manifest = ResultManifest.model_validate_json(artifacts.read(saved.manifest))
    return RuleProjection(
        title=diagnostic.title or str(result.rule_id),
        query=query,
        modules=modules,
        dependencies=dependencies,
        fixtures=json.loads(artifacts.read(result.fixtures)),
        retrieval=json.loads(artifacts.read(result.retrieval_trace)),
        validation=diagnostic.validation,
        previous_manifest=manifest.previous_manifest,
    )
