"""Decode the exact immutable query/modules/dependencies selected by a caller."""

import json

from pydantic import TypeAdapter
from semflow_contracts.errors import ResearchError
from semflow_contracts.toolchains import DependencyPin


def read_rule(rule, artifacts, language):
    # Peers: rule_outputs.export / platform supplemental-rule producer.
    # AGENT: query_hash hashes query bytes; modules and dependencies have their
    # own exact refs. Verify all three, never substitute a platform published row.
    if rule.language != language or rule.query_hash != rule.query.sha256:
        raise ResearchError(
            "identity_mismatch", "Frozen rule language or query digest differs"
        )
    query = artifacts.read(rule.query).decode("utf-8")
    modules = {}
    for ref in rule.modules:
        if ref.schema_version != "codeql.module/1":
            raise ResearchError("unsupported_version", "Unknown named QL module format")
        body = json.loads(artifacts.read(ref))
        if set(body) != {"name", "content"} or body["name"] in modules:
            raise ResearchError(
                "invalid_contract", "Duplicate or invalid named QL module"
            )
        modules[body["name"]] = body["content"]
    dependencies = TypeAdapter(dict[str, DependencyPin]).validate_json(
        artifacts.read(rule.dependencies)
    )
    return (
        query,
        modules,
        {name: pin.model_dump() for name, pin in dependencies.items()},
    )


def import_rules(context, rules):
    from dataclasses import replace

    from semflow_research.adapters.codeql.custom import query_digest
    from semflow_research.runtime.bundle_io import freeze_input
    from semflow_research.runtime.bundle_reader import authorize_records
    from semflow_research.state.models import RuleVersion

    for rule in rules:
        query, modules, dependencies = read_rule(
            rule, context.artifacts, context.spec.language
        )
        producer = rule.query.owner_execution_id
        context = authorize_records(context, (producer,))
        freeze_input(
            context,
            RuleVersion(
                id=rule.rule_id,
                execution_id=producer,
                snapshot_id=context.spec.source.snapshot_id,
                corpus_scope=context.spec.source.snapshot_id,
                language=rule.language,
                title=str(rule.rule_id),
                purpose=rule.purpose,
                strategy="frozen_input",
                query=query,
                modules=modules,
                query_hash=query_digest(query, modules),
                dependencies=dependencies,
                fixtures={},
            ),
            producer,
        )
    context.source_records.update(
        context.spec.source.snapshot_id,
        custom_rule_ids=[str(rule.rule_id) for rule in rules],
    )
    return replace(context, supplemental_rule_ids=tuple(rule.rule_id for rule in rules))
