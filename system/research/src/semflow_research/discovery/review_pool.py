"""Algorithm extracted from app.services.review_pool.

Runtime dependencies are passed explicitly; no platform ORM or configuration.
Changes to JSON require checking the corresponding semflow_contracts/wire peer.
"""

"""Persistent candidate inputs and small cohorts; no trust in scout conclusions."""
import json
from uuid import UUID

from semflow_research.adapters.project_map import module_name
from semflow_research.domain.errors import AuditError
from semflow_research.evidence.context_materials import (
    candidate_materials,
    digest,
    save_json,
)
from semflow_research.evidence.read_tools import project_documents, window_observations
from semflow_research.state.models import Candidate, ExecutionRecord


def prepare_pool(service, *, _kernel):
    service.repository.active(service.execution_id)
    artifact = service.directory / "review-pool.json"
    if artifact.exists():
        saved = json.loads(artifact.read_text())
        if saved["snapshot"] != service.evidence.source_context.snapshot_hash:
            raise AuditError("复核候选池快照不匹配")
        return saved
    audit, inputs = (service.evidence.source_context, service.inputs)
    entries = []
    continuation = getattr(service, "continuation", None)
    with _kernel.records.transaction() as db:
        findings = audit.findings
        if inputs.finding_ids:
            if not set(inputs.finding_ids).issubset({r["id"] for r in findings}):
                raise AuditError("复核告警不属于当前审计")
            findings = [r for r in findings if r["id"] in inputs.finding_ids]
        for finding in findings:
            location = finding["locations"][0]
            try:
                source = (
                    continuation["anchor"]
                    if continuation
                    else service.evidence.read(
                        location["file"],
                        max(1, location["line"] - 8),
                        location["line"] + 12,
                    )
                )
            except AuditError:
                if inputs.paths and (not inputs.finding_ids):
                    continue
                raise
            row = Candidate(
                snapshot_id=audit.id,
                execution_id=service.execution.id,
                origin="static",
                source_ref=audit.finding_candidate_refs.get(finding["id"]),
                static_finding_id=finding["id"],
                identity_key="static:" + finding["id"],
                novelty="baseline",
                location=location,
                title=finding["rule"],
                description=finding["message"],
                evidence_ids=[source["id"]],
            )
            db.save(row)
            entries.append(
                {
                    "candidate_id": str(row.id),
                    "origin": "static",
                    "static_alert": finding,
                    "location": location,
                    "hypothesis": finding["message"],
                    "evidence_ids": [source["id"]],
                }
            )
        scouts = (
            db.list(
                Candidate,
                snapshot_id=audit.id,
                origin="ai",
                execution_id__in=[
                    r.id for r in _kernel.records.list(ExecutionRecord, kind="scout")
                ],
            )
            if inputs.include_scout
            else []
        )
        if inputs.scout_candidate_ids:
            if not set(inputs.scout_candidate_ids).issubset({r.id for r in scouts}):
                raise AuditError("粗筛候选不属于本次审计或未开启粗筛输入")
            scouts = [r for r in scouts if r.id in inputs.scout_candidate_ids]
        unique = {r.identity_key: r for r in scouts}
        for original in unique.values():
            try:
                service.evidence.allowed(original.location["file"])
            except AuditError:
                if inputs.paths and (not inputs.scout_candidate_ids):
                    continue
                raise
            materials = (
                continuation["pages"]
                if continuation
                else candidate_materials(service.evidence, [original], _kernel=_kernel)
            )
            scout_stage = db.get(ExecutionRecord, original.execution_id)
            metadata = next(
                (
                    h
                    for unit in scout_stage.result.get("units", [])
                    for h in unit.get("hypotheses", [])
                    if h["candidate_id"] == str(original.id)
                ),
                None,
            )
            row = Candidate(
                snapshot_id=audit.id,
                execution_id=service.execution.id,
                origin="ai",
                source_ref=original.source_ref,
                title=original.title,
                description=original.description,
                weakness=original.weakness,
                identity_key=original.identity_key,
                novelty="unverified",
                location=original.location,
                related_target=str(original.id),
                evidence_ids=[m["id"] for m in materials],
            )
            db.save(row)
            entries.append(
                {
                    "candidate_id": str(row.id),
                    "source_candidate_id": str(original.id),
                    "origin": "scout",
                    "location": row.location,
                    "weakness": row.weakness,
                    "hypothesis": metadata or original.description,
                    "evidence_ids": row.evidence_ids,
                }
            )
        stage = db.one(ExecutionRecord, id=service.execution.id)
        if stage.status == "cancelled":
            from semflow_research.domain.errors import ExecutionCancelled

            raise ExecutionCancelled("复核已取消")
        pool = {
            "snapshot": audit.snapshot_hash,
            "entries": entries,
            "inputs": inputs.model_dump(mode="json"),
        }
        stage.result = {**stage.result, "pool": pool}
        db.save(stage)
        db.commit()
    save_json(artifact, pool)
    return pool


def pool_for_resume(service, *, _kernel):
    path = service.directory / "review-pool.json"
    stage = service.repository.get(service.execution_id)
    if not path.exists() and stage.result.get("pool"):
        save_json(path, stage.result["pool"])
    pool = prepare_pool(service, _kernel=_kernel)
    if stage.result.get("pool") and digest(pool) != digest(stage.result["pool"]):
        raise AuditError("复核候选池被修改")
    expected_inputs = service.inputs.model_dump(mode="json")
    if "supplement_insufficient" not in pool["inputs"]:
        expected_inputs.pop("supplement_insufficient")
    if pool["inputs"] != expected_inputs:
        raise AuditError("复核范围或预算已变化")
    return pool


def batches(pool, size, prioritize_scout=False, coherent_conditions=False):
    from semflow_research.discovery.discovery_context import property_for

    entries = sorted(
        pool["entries"],
        key=lambda r: (
            0
            if coherent_conditions
            else 0
            if prioritize_scout and r["origin"] == "scout"
            else 1,
            module_name(r["location"]["file"]),
            r["location"]["file"],
            property_for(r) if coherent_conditions else "",
            r["location"]["line"],
            r["candidate_id"],
        ),
    )
    if not coherent_conditions:
        return [entries[start : start + size] for start in range(0, len(entries), size)]
    groups = []
    for entry in entries:
        key = (entry["location"]["file"], property_for(entry))
        if (
            not groups
            or len(groups[-1]) >= size
            or key != (groups[-1][0]["location"]["file"], property_for(groups[-1][0]))
        ):
            groups.append([])
        groups[-1].append(entry)
    return groups


def fit_batches(service, schedule, *, _kernel):
    """Split oversized cohorts before model calls; never discard target evidence."""
    from semflow_research.adapters.context_packing import context_size, fit_navigation

    fitted = []
    for entries in schedule:
        if len(entries) > 1:
            context = fit_navigation(
                batch_context(service, entries, _kernel=_kernel),
                service.inputs.max_context_chars,
            )
            if context_size(context) > service.inputs.max_context_chars:
                middle = len(entries) // 2
                fitted.extend(
                    fit_batches(
                        service, [entries[:middle], entries[middle:]], _kernel=_kernel
                    )
                )
                continue
        fitted.append(entries)
    return fitted


def batch_context(service, entries, *, _kernel):
    ids = [UUID(r["candidate_id"]) for r in entries]
    with _kernel.records.transaction() as db:
        candidates = db.list(Candidate, execution_id=service.execution.id, id__in=ids)
    continuation = getattr(service, "continuation", None)
    if continuation:
        materials = list(continuation["pages"])
    else:
        materials = candidate_materials(service.evidence, candidates, _kernel=_kernel)
        materials.extend(project_documents(service.evidence))
    materials = list({r["id"]: r for r in materials}.values())
    bindings = []
    if service.execution.method_version in {"5", "6", "7", "8", "9", "10", "11", "12"}:
        from semflow_research.adapters.python_bindings import location_bindings

        bindings = location_bindings(service.evidence, [r["location"] for r in entries])
    if service.execution.method_version in {"6", "7", "8", "9", "10", "11", "12"}:
        from semflow_research.discovery.review_tools import prime_source_pages

        if not continuation:
            materials = prime_source_pages(
                service.evidence,
                materials,
                entries,
                include_related=service.execution.method_version
                in {"7", "8", "9", "10", "11", "12"},
            )
        entries = [
            {
                **r,
                "hypothesis": {
                    k: v
                    for k, v in r["hypothesis"].items()
                    if k
                    in {
                        "title",
                        "weakness",
                        "primary_location",
                        "security_condition",
                        "observation",
                        "security_property",
                        "operation_quote",
                        "endpoint",
                        "missing_premises",
                        "unknown_premises",
                        "runtime_unknowns",
                    }
                }
                if isinstance(r["hypothesis"], dict)
                else r["hypothesis"],
            }
            for r in entries
        ]
        from semflow_research.evidence.read_tools import grounded

        entries = [
            {
                **r,
                "evidence_ids": [
                    m["id"] for m in materials if grounded([m], r["location"])
                ],
            }
            for r in entries
        ]
    files = [
        p.relative_to(service.evidence.root).as_posix()
        for p in service.evidence.files()
    ]
    framework_reference = []
    if service.execution.method_version in {"7", "8", "9", "10", "11", "12"} and any(
        r["reference"].get("file", "").endswith(".ejs")
        for r in materials
        if r["kind"] == "code"
    ):
        framework_reference = [
            {
                "syntax": "EJS",
                "source": "CodeQL javascript-all 2.4.0 semmle/javascript/frameworks/Templating.qll:570-583 (locally verified)",
                "facts": {
                    "<%= expression %>": "HTML-escaped interpolation by default",
                    "<%- expression %>": "Raw interpolation; output is not escaped",
                },
                "limit": "Grammar background, not code evidence or a confirmed data flow. Verify actual renderer/configuration. HTML escaping is not universal protection in JavaScript/URL contexts; includes are not automatically tainted sinks.",
            }
        ]
    context = {
        **(
            {
                "framework_syntax_reference": framework_reference,
                "citation_contract": {
                    "supported_or_excluded": "Cite at least one target evidence_id covering the candidate primary location, plus actual supporting/counterevidence IDs from related modules. A guard in another file alone cannot ground a verdict at the target. Use insufficient if unresolved.",
                    "target_source_ids": {
                        r["candidate_id"]: r["evidence_ids"] for r in entries
                    },
                    "reason": "Target source and related counterevidence serve different proof obligations; both bodies are supplied.",
                },
            }
            if service.execution.method_version in {"7", "8", "9", "10", "11", "12"}
            else {}
        ),
        **({"prior_review": continuation["summary"]} if continuation else {}),
        "snapshot": service.evidence.source_context.snapshot_hash,
        "language": service.evidence.source_context.language,
        "paths": service.inputs.paths,
        "targets": entries,
        "anchors": [],
        "evidence": materials,
        "source_windows": window_observations(service.evidence, materials),
        "symbol_bindings": bindings,
        "allow_supplementary_findings": service.inputs.discover,
        "source_inventory": {
            "files": files[:80],
            "total_files": len(files),
            "omitted_files": max(0, len(files) - 80),
            "meaning": "Selected-language files within selected snapshot scope; names are navigation clues, not proof their contents were inspected",
        },
        "assessment_boundary": "Judge source-level security conditions in this immutable snapshot and selected paths. Deployed exploitability, external services and unprovided production configurations are separate unknowns, not implied properties of this snapshot.",
        "evidence_status": "Actual source/documents already read by the host. Cite supplied IDs without re-reading. Prior detector hypotheses require verification, not prior reasoning replay.",
        "tool_trace": [],
        "model_recommendations_only": True,
        "scope_limit": "Current batch only; related files can be read, other candidates are not assumed reviewed",
    }
    if service.execution.method_version in {"8", "9", "10", "11", "12"}:
        from semflow_research.discovery.discovery_context import augment_context

        context = augment_context(service, context)
        context["source_windows"] = window_observations(
            service.evidence, context["evidence"]
        )
    return context
