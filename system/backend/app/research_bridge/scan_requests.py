"""Freeze scan settings and platform-selected rules, without copying algorithms."""

import hashlib
from types import SimpleNamespace
from uuid import UUID

from semflow_contracts.common import canonical_bytes
from semflow_contracts.rule_values import RuleRef
from semflow_contracts.runs import validate_spec
from semflow_research.public.artifacts import commit
from semflow_research.public.sources import tree_digest

from app.contracts.scouting import ScoutRequest
from app.research_bridge.requests import freeze_stage, research_root


def freeze_scan(binding, audit):
    # Reuse the exact same platform policy conversion as standalone Scout. This
    # synthetic DTO creates no platform stage or algorithm state by itself.
    stage = SimpleNamespace(
        kind="scout",
        prompt_version="7",
        inputs=ScoutRequest().model_dump(mode="json"),
        model_config_snapshot=binding.policy,
    )
    spec, resources = freeze_stage(binding, stage, audit)
    name, version = audit.query_pack.split("@", 1)
    pack = resources.CODEQL_PACK_PATH / name / version
    suite = pack / audit.suite
    scan = {
        "build_profile": "none",
        "query_pack": {"name": name, "version": version, "digest": tree_digest(pack)},
        "suite": {
            "name": audit.suite,
            "digest": hashlib.sha256(suite.read_bytes()).hexdigest(),
        },
        "supplemental_rules": [
            freeze_rule(identifier, audit, binding).model_dump(mode="json")
            for identifier in audit.custom_rule_ids
        ],
    }
    value = spec.model_dump(mode="json")
    dual = audit.coverage.get("pipeline_version") == "2"
    value.update(
        operation="discover" if dual else "scan",
        inputs={
            "scan": scan,
            "scout": value["inputs"],
            "scout_method_version": "7",
            "required_branches": ["scan"],
        }
        if dual
        else scan,
    )
    value["implementation"].update(
        method_id="semflow.discovery" if dual else "semflow.scan", method_version="1"
    )
    if not dual:
        value.update(model=None, prompts=[])
    spec = validate_spec(value)
    binding.request = spec.model_dump(mode="json")
    return spec, resources


def freeze_rule(identifier, audit, binding):
    from app.services.rules_execution import owned_published_rule

    rule = owned_published_rule(
        UUID(identifier), audit.owner_id, audit.language, allow_retired=True
    )
    arguments = {"root": research_root(), "execution_id": binding.execution_id}
    query = commit(
        rule.query.encode(),
        kind="query",
        schema_version="codeql.query/1",
        media_type="text/plain",
        **arguments,
    )
    modules = tuple(
        commit(
            canonical_bytes({"name": name, "content": text}),
            kind="rule_modules",
            schema_version="codeql.module/1",
            **arguments,
        )
        for name, text in sorted(rule.modules.items())
    )
    dependencies = commit(
        canonical_bytes(rule.dependencies),
        kind="dependencies",
        schema_version="codeql.dependencies/1",
        **arguments,
    )
    # WIRE-SEND:research.run — peer: runtime.rule_inputs.read_rule / scan_supplements.apply.
    # AGENT: publication/ownership stays here; send exact selected query, named
    # modules and dependencies. The kernel never queries the platform rule table.
    return RuleRef(
        rule_id=rule.id,
        version=str(rule.id),
        purpose=rule.purpose,
        language=rule.language,
        query=query,
        query_hash=query.sha256,
        modules=modules,
        dependencies=dependencies,
    )
