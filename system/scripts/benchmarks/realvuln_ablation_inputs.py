"""Isolate review arms in new audits with frozen upstream evidence only."""

import copy
import hashlib
from uuid import UUID, uuid4

from app.adapters.artifacts import ArtifactStore
from app.core.db import engine
from app.models import User
from app.persistence.audit_models import AuditRun
from app.persistence.stage_models import Candidate, Evidence, StageRun
from scripts.benchmarks.realvuln_ablation_io import read
from scripts.benchmarks.realvuln_prepare import save
from sqlmodel import Session


def register(project, group, origin, output, stage_catalog):
    receipt = output / "arms" / group / "system" / project / "input.json"
    if receipt.exists():
        return read(receipt)
    scout = read(origin / "system" / project / "scout.json")
    static = read(origin / "static" / project / "result.json")
    if static["status"] != "succeeded":
        raise RuntimeError("A failed baseline cannot be used as a qualified input")
    audit_id, owner = uuid4(), uuid4()
    with Session(engine) as db:
        db.add(
            User(
                id=owner,
                email=f"ablation-{owner}@research.invalid",
                hashed_password="disabled-research",
                is_active=False,
            )
        )
        db.commit()
        audit = AuditRun(
            id=audit_id,
            owner_id=owner,
            source_run_id=audit_id,
            project_name=project,
            language="python",
            status="completed",
            phase="ablation_review_inputs",
            snapshot_hash=static["snapshot"],
            query_pack=static["pack"],
            suite=static["suite"],
            codeql_version=read(origin / "config.json")["codeql_cli"],
            findings=static["rounds"][0]["findings"] if group in {"D", "F"} else [],
            coverage={
                "benchmark_arm": group,
                "baseline_receipt": str(origin / "static" / project / "result.json"),
                "codeql_input_selected": group in {"D", "F"},
                "scout_input_selected": group in {"E", "F"},
            },
        )
        db.add(audit)
        db.commit()
        mapping = {}
        if group in {"E", "F"}:
            cloned_stage = StageRun(
                audit_id=audit_id,
                kind="scout",
                status="completed",
                phase="frozen_upstream_import",
                prompt_version="7",
                inputs={"import_only": True},
                result={"upstream_reused": True},
            )
            db.add(cloned_stage)
            db.commit()
            db.refresh(cloned_stage)
            evidence_map = {}
            for old in scout["candidates"]:
                evidence_ids = []
                for identifier in old["evidence_ids"]:
                    if identifier not in evidence_map:
                        row = db.get(Evidence, UUID(identifier))
                        if (
                            row is None
                            or str(row.audit_id) != scout["stage"]["audit_id"]
                            or row.snapshot_hash != static["snapshot"]
                            or hashlib.sha256(row.content.encode()).hexdigest()
                            != row.digest
                        ):
                            raise RuntimeError(
                                "Inherited evidence identity/content mismatch"
                            )
                        evidence = Evidence(
                            audit_id=audit_id,
                            stage_id=cloned_stage.id,
                            kind=row.kind,
                            snapshot_hash=row.snapshot_hash,
                            reference=row.reference,
                            content=row.content,
                            digest=row.digest,
                        )
                        db.add(evidence)
                        db.flush()
                        evidence_map[identifier] = str(evidence.id)
                    evidence_ids.append(evidence_map[identifier])
                candidate = Candidate(
                    audit_id=audit_id,
                    stage_id=cloned_stage.id,
                    origin="ai",
                    title=old["title"],
                    description=old["description"],
                    weakness=old["weakness"],
                    location=old["location"],
                    identity_key=old["identity_key"],
                    evidence_ids=evidence_ids,
                    status="pending",
                    model_assessment="pending",
                    related_target=old.get("related_target"),
                    novelty=old["novelty"],
                )
                db.add(candidate)
                db.flush()
                mapping[old["id"]] = str(candidate.id)
            source_stages = {c["stage_id"] for c in scout["candidates"]} | {
                scout["stage_id"]
            }
            units = []
            for identifier in sorted(source_stages):
                for unit in stage_catalog[identifier]["stage"]["result"].get(
                    "units", []
                ):
                    hypotheses = []
                    for original in unit.get("hypotheses", []):
                        if original["candidate_id"] not in mapping:
                            continue
                        hypothesis = copy.deepcopy(original)
                        hypothesis["candidate_id"] = mapping[original["candidate_id"]]
                        hypothesis["evidence_ids"] = [
                            evidence_map[i]
                            for i in original.get("evidence_ids", [])
                            if i in evidence_map
                        ]
                        hypotheses.append(hypothesis)
                    if hypotheses:
                        units.append({**unit, "hypotheses": hypotheses})
            cloned_stage.result = {
                "upstream_reused": True,
                "units": units,
                "original_stage_ids": sorted(source_stages),
            }
            db.add(cloned_stage)
            db.commit()
    directory = ArtifactStore().directory(str(audit_id))
    (directory / "source").symlink_to(
        origin / "sources" / project, target_is_directory=True
    )
    (directory / "database").symlink_to(
        origin / "static" / project / "database", target_is_directory=True
    )
    result = {
        "project_id": project,
        "group": group,
        "audit_id": str(audit_id),
        "snapshot": static["snapshot"],
        "source_candidate_mapping": mapping,
        "static_findings_selected": len(static["rounds"][0]["findings"])
        if group in {"D", "F"}
        else 0,
        "scout_candidates_selected": len(mapping),
        "no_review_answers_imported": True,
        "origin": str(origin),
    }
    save(receipt, result)
    return result
