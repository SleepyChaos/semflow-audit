"""Three mandatory inputs: project code, vulnerability description and dual RAG."""

from sqlmodel import Session

from app.adapters.codeql.custom import fixed_dependencies
from app.adapters.retrieval.dual_corpus import retrieve_both
from app.core.db import engine
from app.domain.audit import AuditError
from app.persistence.stage_models import Candidate
from app.services.context_materials import candidate_materials, digest, save_json
from app.services.evidence import EvidenceService
from app.services.semantic_inspection import SemanticInspection


def prepare_rule_materials(service):
    s = service
    evidence = EvidenceService(str(s.audit.id), s.stage_id, [])
    with Session(engine) as session:
        candidate = (
            session.get(Candidate, s.inputs.candidate_id)
            if s.inputs.candidate_id
            else None
        )
    if s.inputs.candidate_id and (
        candidate is None
        or candidate.audit_id != s.audit.id
        or candidate.status != "confirmed"
    ):
        raise AuditError("规则目标不是本审计已确认漏洞")
    identity = preparation_identity(s, candidate)
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
    materials = candidate_materials(evidence, [candidate]) if candidate else []
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
        "baseline_status": s.audit.status,
        "evidence_ids": candidate.evidence_ids
        if candidate
        else [m["id"] for m in materials],
    }
    version = fixed_dependencies(s.audit.language)[f"codeql/{s.audit.language}-all"][
        "version"
    ]

    def retrieve():
        return retrieve_both(
            s.audit.owner_id,
            s.audit.language,
            s.inputs.requirement + " " + target["weakness"],
            version,
            mode=s.experiment.get("retrieval_mode", "auto"),
            routed=s.experiment.get("collection_routing", True),
            document_ids=s.experiment.get("corpus_document_ids"),
            enhanced=s.stage.prompt_version in {"7", "8"},
            exact_cwe=s.stage.prompt_version == "8",
        )

    early_rag = s.stage.prompt_version == "8" and s.experiment.get(
        "rag_before_inspection", False
    )
    knowledge = retrieve() if early_rag else []
    reference_context = None
    if s.stage.prompt_version == "8" and s.experiment.get(
        "source_preparation_context", True
    ):
        from app.services.rule_preparation_context import preparation_context

        reference_context = preparation_context(
            s, target, knowledge, evidence, materials
        )
    inspection = SemanticInspection(
        evidence,
        s.provider,
        s.directory,
        s.repository,
        "rule",
        progressive=s.stage.prompt_version in {"7", "8"}
        and s.experiment.get("progress_feedback", True),
        reference_context=reference_context,
        require_grounded_source=s.stage.prompt_version == "8",
    ).inspect([target], materials)
    if not early_rag:
        knowledge = retrieve()
    bundle = {"target": target, "inspection": inspection, "knowledge": knowledge}
    if s.stage.prompt_version == "8":
        # Baseline observations are frozen together with the source and retrieval.
        from app.services.rule_preparation_context import preparation_context

        bundle["preparation_context"] = preparation_context(
            s, target, [], evidence, materials
        )
    save_json(s.directory / "rule-materials.json", bundle)
    save_json(
        s.directory / "rule-materials-receipt.json",
        {"identity": identity, "materials_digest": digest(bundle)},
    )
    s.repository.update(
        s.stage_id,
        phase="materials_ready",
        model=s.provider.model,
        result={"retrieval": knowledge, "materials_artifact": "rule-materials.json"},
    )
    # The graph carries a reference; detailed code and facts remain in artifacts.
    return {"materials_id": "rule-materials.json", "materials_digest": digest(bundle)}


def load_rule_materials(service, state):
    import json

    name = state.get("materials_id")
    if name != "rule-materials.json":
        raise AuditError("规则生成材料引用无效")
    bundle = json.loads((service.directory / name).read_text())
    if digest(bundle) != state.get("materials_digest"):
        raise AuditError("规则生成材料被修改")
    EvidenceService(str(service.audit.id), service.stage_id, [])
    with Session(engine) as session:
        candidate = (
            session.get(Candidate, service.inputs.candidate_id)
            if service.inputs.candidate_id
            else None
        )
    if service.inputs.candidate_id and (
        candidate is None
        or candidate.status != "confirmed"
        or candidate.audit_id != service.audit.id
    ):
        raise AuditError("规则目标确认状态变化")
    if bundle["inspection"]["snapshot_hash"] != service.audit.snapshot_hash:
        raise AuditError("规则材料快照不匹配")
    return bundle


def preparation_identity(service, candidate):
    from app.adapters.retrieval.embedding_identity import embedding_identity
    from app.core.audit_config import audit_settings

    return digest(
        {
            "snapshot": service.audit.snapshot_hash,
            **(
                {
                    "prompt_version": service.stage.prompt_version,
                    "progress_feedback": service.experiment.get(
                        "progress_feedback", True
                    ),
                }
                if service.stage.prompt_version in {"7", "8"}
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
                    "baseline_digest": digest(service.audit.findings),
                }
                if service.stage.prompt_version == "8"
                else {}
            ),
            "inputs": service.inputs.model_dump(mode="json"),
            "target": candidate.model_dump(mode="json") if candidate else None,
            "dependencies": fixed_dependencies(service.audit.language),
            "retrieval_mode": service.experiment.get("retrieval_mode", "auto"),
            "collection_routing": service.experiment.get("collection_routing", True),
            "corpus_document_ids": service.experiment.get("corpus_document_ids"),
            "embedding_identity": embedding_identity()
            if audit_settings.EMBEDDING_MODEL
            else None,
        }
    )
