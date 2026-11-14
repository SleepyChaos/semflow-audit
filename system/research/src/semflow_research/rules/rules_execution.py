"""Only explicitly frozen supplemental rules may be executed by a kernel."""

import json
from uuid import UUID

from semflow_research.adapters.artifacts import ArtifactStore
from semflow_research.adapters.codeql.custom import (
    prepare_query,
    query_digest,
    run_query,
)
from semflow_research.domain.errors import AuditError
from semflow_research.state.models import RuleVersion


def frozen_supplement_rule(
    identifier, corpus_scope, language, *, allow_retired=False, _kernel
):
    # Publication/visibility belongs to the platform producer; CLI explicitly selects input rules.
    # AGENT: never replace this frozen whitelist with a platform-table lookup.
    if str(identifier) not in set(map(str, _kernel.supplemental_rule_ids)):
        raise AuditError("补充规则没有包含在本次冻结输入中", code="identity_error")
    rule = _kernel.records.get(RuleVersion, identifier)
    if (
        rule is None
        or rule.language != language
        or query_digest(rule.query, rule.modules) != rule.query_hash
    ):
        raise AuditError("冻结补充规则的身份、语言或摘要不匹配", code="integrity_error")
    return rule


def execute_evidence_query(evidence, identifier):
    context = evidence._kernel
    source = evidence.source_context
    rule = frozen_supplement_rule(
        UUID(str(identifier)), source.corpus_scope, source.language, _kernel=context
    )
    directory = (
        ArtifactStore(_kernel=context).directory(evidence.execution_id)
        / "evidence-queries"
        / str(rule.id)
    )
    pack = directory / "pack"
    prepare_query(
        pack,
        source.language,
        rule.query,
        rule.modules,
        rule.dependencies,
    )
    findings = run_query(
        context.baseline_directory / "database",
        pack,
        directory / "results.sarif",
        directory / "execution.log",
        source.snapshot_hash,
        _kernel=context,
    )
    return evidence.record(
        "query",
        json.dumps(findings, ensure_ascii=False),
        {
            "rule_id": str(rule.id),
            "query_hash": rule.query_hash,
            "raw_output": str(
                (directory / "results.sarif").relative_to(context.workspace)
            ),
        },
    )
