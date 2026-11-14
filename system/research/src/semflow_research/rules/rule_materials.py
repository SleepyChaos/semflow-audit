"""Algorithm extracted from app.services.rule_materials.

Runtime dependencies are passed explicitly; no platform ORM or configuration.
Changes to JSON require checking the corresponding semflow_contracts/wire peer.
"""

"""Three mandatory inputs: project code, vulnerability description and dual RAG."""
from semflow_research.adapters.codeql.custom import fixed_dependencies
from semflow_research.adapters.retrieval.dual_corpus import retrieve_both
from semflow_research.domain.errors import AuditError
from semflow_research.evidence.context_materials import (
    candidate_materials,
    digest,
    save_json,
)
from semflow_research.evidence.evidence import EvidenceService
from semflow_research.evidence.semantic_inspection import SemanticInspection
from semflow_research.state.models import Candidate


def prepare_rule_materials(service, *, _kernel):
    s = service
    evidence = EvidenceService(
        str(s.source_context.id), s.execution_id, [], _kernel=_kernel
    )
    with _kernel.records.transaction() as session:
        candidate = (
            session.get(Candidate, s.inputs.candidate_id)
            if s.inputs.candidate_id
            else None
        )
    if s.inputs.candidate_id and (
        candidate is None
        or candidate.snapshot_id != s.source_context.id
        or candidate.status != "confirmed"
    ):
        raise AuditError("规则目标不是本审计已确认漏洞")
    identity = preparation_identity(s, candidate, _kernel=_kernel)
    corpus_scope = _kernel.corpus_snapshot.snapshot_id
    saved = s.directory / "rule-materials.json"
    if saved.exists():
        import json

        bundle = json.loads(saved.read_text())
        receipt = json.loads((s.directory / "rule-materials-receipt.json").read_text())
        if receipt["identity"] != identity or receipt["materials_digest"] != digest(
            bundle
        ):
            raise AuditError("规则准备材料或输入配置已变化")
        return {
            "materials_id": "rule-materials.json",
            "materials_digest": digest(bundle),
        }
    materials = (
        candidate_materials(evidence, [candidate], _kernel=_kernel) if candidate else []
    )
    for file in s.inputs.source_paths:
        materials.append(evidence.read(file, 1, 100))
    if not materials and candidate and candidate.location.get("file"):
        line = max(1, candidate.location.get("line", 1))
        materials.append(
            evidence.read(candidate.location["file"], max(1, line - 15), line + 35)
        )
    if not any(m["kind"] == "code" for m in materials):
        raise AuditError(
            "规则生成缺少源码正文，请选择确认漏洞或提供 source_paths",
            code="materials_missing",
        )
    target = {
        "candidate_id": str(candidate.id) if candidate else None,
        "title": candidate.title if candidate else s.inputs.requirement,
        "description": candidate.description if candidate else s.inputs.requirement,
        "status": candidate.status if candidate else "unconfirmed_requirement",
        "weakness": candidate.weakness if candidate else "unknown",
        "location": candidate.location if candidate else {},
        "baseline_status": s.source_context.status,
        "evidence_ids": candidate.evidence_ids
        if candidate
        else [m["id"] for m in materials],
    }
    version = fixed_dependencies(s.source_context.language, _kernel=_kernel)[
        f"codeql/{s.source_context.language}-all"
    ]["version"]

    def retrieve():
        return retrieve_both(
            corpus_scope,
            s.source_context.language,
            s.inputs.requirement + " " + target["weakness"],
            version,
            mode=s.experiment.get("retrieval_mode", "auto"),
            routed=s.experiment.get("collection_routing", True),
            document_ids=s.experiment.get("corpus_document_ids"),
            enhanced=s.execution.method_version in {"7", "8"},
            exact_cwe=s.execution.method_version == "8",
            _kernel=_kernel,
        )

    early_rag = s.execution.method_version == "8" and s.experiment.get(
        "rag_before_inspection", False
    )
    knowledge = retrieve() if early_rag else []
    reference_context = None
    if s.execution.method_version == "8" and s.experiment.get(
        "source_preparation_context", True
    ):
        from semflow_research.rules.rule_preparation_context import preparation_context

        reference_context = preparation_context(
            s, target, knowledge, evidence, materials, _kernel=_kernel
        )
    inspection = SemanticInspection(
        evidence,
        s.provider,
        s.directory,
        s.repository,
        "rule",
        progressive=s.execution.method_version in {"7", "8"}
        and s.experiment.get("progress_feedback", True),
        reference_context=reference_context,
        require_grounded_source=s.execution.method_version == "8",
        _kernel=_kernel,
    ).inspect([target], materials)
    if not early_rag:
        knowledge = retrieve()
    bundle = {"target": target, "inspection": inspection, "knowledge": knowledge}
    if s.execution.method_version == "8":
        from semflow_research.rules.rule_preparation_context import preparation_context

        bundle["preparation_context"] = preparation_context(
            s, target, [], evidence, materials, _kernel=_kernel
        )
    save_json(s.directory / "rule-materials.json", bundle)
    save_json(
        s.directory / "rule-materials-receipt.json",
        {"identity": identity, "materials_digest": digest(bundle)},
    )
    s.repository.update(
        s.execution_id,
        phase="materials_ready",
        model=s.provider.model,
        result={"retrieval": knowledge, "materials_artifact": "rule-materials.json"},
    )
    return {"materials_id": "rule-materials.json", "materials_digest": digest(bundle)}


def load_rule_materials(service, state, *, _kernel):
    import json

    name = state.get("materials_id")
    if name != "rule-materials.json":
        raise AuditError("规则生成材料引用无效")
    bundle = json.loads((service.directory / name).read_text())
    if digest(bundle) != state.get("materials_digest"):
        raise AuditError("规则生成材料被修改")
    EvidenceService(
        str(service.source_context.id), service.execution_id, [], _kernel=_kernel
    )
    with _kernel.records.transaction() as session:
        candidate = (
            session.get(Candidate, service.inputs.candidate_id)
            if service.inputs.candidate_id
            else None
        )
    if service.inputs.candidate_id and (
        candidate is None
        or candidate.status != "confirmed"
        or candidate.snapshot_id != service.source_context.id
    ):
        raise AuditError("规则目标确认状态变化")
    if bundle["inspection"]["snapshot_hash"] != service.source_context.snapshot_hash:
        raise AuditError("规则材料快照不匹配")
    return bundle


def preparation_identity(service, candidate, *, _kernel):
    from semflow_research.adapters.retrieval.embedding_identity import (
        embedding_identity,
    )

    return digest(
        {
            "snapshot": service.source_context.snapshot_hash,
            **(
                {
                    "method_version": service.execution.method_version,
                    "progress_feedback": service.experiment.get(
                        "progress_feedback", True
                    ),
                }
                if service.execution.method_version in {"7", "8"}
                else {}
            ),
            **(
                {
                    "source_preparation_context": service.experiment.get(
                        "source_preparation_context", True
                    ),
                    "rag_before_inspection": service.experiment.get(
                        "rag_before_inspection", False
                    ),
                    "baseline_digest": digest(service.source_context.findings),
                }
                if service.execution.method_version == "8"
                else {}
            ),
            "inputs": service.inputs.model_dump(mode="json"),
            "target": candidate.model_dump(mode="json") if candidate else None,
            "dependencies": fixed_dependencies(
                service.source_context.language, _kernel=_kernel
            ),
            "retrieval_mode": service.experiment.get("retrieval_mode", "auto"),
            "collection_routing": service.experiment.get("collection_routing", True),
            "corpus_document_ids": service.experiment.get("corpus_document_ids"),
            "embedding_identity": embedding_identity(_kernel=_kernel)
            if _kernel.settings.EMBEDDING_MODEL
            else None,
        }
    )
