"""Private research audit bridge, preserving source/DB identity and run receipts."""

import json
import shutil
import time
from pathlib import Path
from uuid import UUID, uuid4

from app.adapters.ai.policy import policy_snapshot
from app.adapters.ai.provider import CompatibleModel
from app.adapters.artifacts import ArtifactStore
from app.adapters.snapshot import snapshot_digest
from app.core.db import engine
from app.models import User
from app.persistence.audit_models import AuditRun
from app.persistence.stage_models import Candidate, StageRun
from app.persistence.stage_repository import StageRepository
from sqlmodel import Session, select

from scripts.benchmarks.formal_freeze import OUTPUT, save


def register_audit(project_id, output=None):
    output = output or OUTPUT
    path = output / "audits" / f"{project_id}.json"
    if path.exists():
        return json.loads(path.read_text())["audit_id"]
    rows = json.loads((output / "inputs.json").read_text())["records"]
    if (output / "inputs-derived.json").exists():
        rows += json.loads((output / "inputs-derived.json").read_text())["records"]
    row = next(r for r in rows if r["id"] == project_id)
    baseline_dir = output / "static" / project_id
    baseline = json.loads((baseline_dir / "result.json").read_text())
    if baseline["status"] != "succeeded":
        raise RuntimeError("Failed static baseline cannot become a successful audit")
    source = Path(row["source"])
    if snapshot_digest(source) != baseline["snapshot"]:
        raise RuntimeError("Source changed after baseline")
    audit_id, owner = uuid4(), uuid4()
    directory = ArtifactStore().directory(str(audit_id))
    # Core-stage benchmarking only: private root aliases retain CodeQL absolute source
    # identity. This does not claim that the web upload file-count limit was tested.
    (directory / "source").symlink_to(source, target_is_directory=True)
    (directory / "database").symlink_to(
        baseline_dir / "database", target_is_directory=True
    )
    shutil.copyfile(baseline_dir / "round-1.sarif", directory / "results.sarif")
    with Session(engine) as db:
        db.add(
            User(
                id=owner,
                email=f"formal-{owner}@research.invalid",
                hashed_password="disabled-research",
                is_active=False,
            )
        )
        db.commit()
        db.add(
            AuditRun(
                id=audit_id,
                owner_id=owner,
                source_run_id=audit_id,
                project_name=project_id,
                language=row["language"],
                status="completed",
                phase="completed",
                snapshot_hash=baseline["snapshot"],
                query_pack=baseline["pack"],
                suite=baseline["suite"],
                codeql_version=json.loads((output / "config.json").read_text())[
                    "codeql_cli"
                ],
                findings=baseline["rounds"][0]["findings"],
                coverage={
                    "research_bridge": True,
                    "upload_limit_bypassed": row["files"] > 2000,
                },
            )
        )
        db.commit()
    save(
        path,
        {
            "project_id": project_id,
            "audit_id": str(audit_id),
            "owner_id": str(owner),
            "snapshot": baseline["snapshot"],
            "core_stage_benchmark_not_upload_or_gui": True,
            "upload_file_count_limit_exceeded": row["files"] > 2000,
        },
    )
    return str(audit_id)


def new_stage(audit_id, kind, version, inputs, experiment=None):
    policy = policy_snapshot()
    policy.update(max_calls=12, max_seconds=240)
    if experiment is not None:
        policy["rule_experiment"] = experiment
    with Session(engine) as db:
        row = StageRun(
            audit_id=UUID(audit_id),
            kind=kind,
            prompt_version=version,
            inputs=inputs,
            model_config_snapshot=policy,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return str(row.id)


def run_stage(stage_id, service_type, graph_builder):
    repository = StageRepository()
    if not repository.claim(stage_id):
        return stage_record(stage_id, 0)
    provider = CompatibleModel()
    provider.bind_stage(stage_id, repository.get(stage_id).prompt_version)
    began = time.perf_counter()
    try:
        service = service_type(stage_id, provider)
        graph_builder(service).invoke({"stage_id": stage_id}, {"recursion_limit": 60})
    except Exception as exc:  # noqa: BLE001 - persist failure at benchmark boundary
        repository.update(
            stage_id,
            status="failed",
            error=str(exc)[:1000],
            usage=provider.usage,
            result={
                **repository.get(stage_id).result,
                "benchmark_error_type": type(exc).__name__,
            },
        )
    return stage_record(stage_id, time.perf_counter() - began)


def stage_record(stage_id, seconds):
    with Session(engine) as db:
        stage = db.get(StageRun, UUID(stage_id))
        candidates = db.exec(
            select(Candidate).where(Candidate.stage_id == stage.id)
        ).all()
        return {
            "stage_id": stage_id,
            "wall_seconds": seconds,
            "stage": stage.model_dump(mode="json"),
            "candidates": [r.model_dump(mode="json") for r in candidates],
        }


def checkpoint_stage(path, create, service_type, graph_builder):
    if path.exists():
        return json.loads(path.read_text())
    marker = path.with_suffix(".started.json")
    if marker.exists():
        raise RuntimeError("Interrupted model stage requires explicit receipt recovery")
    stage_id = create()
    save(marker, {"stage_id": stage_id})
    result = run_stage(stage_id, service_type, graph_builder)
    save(path, result)
    print(
        json.dumps(
            {
                "stage_id": stage_id,
                "kind": result["stage"]["kind"],
                "status": result["stage"]["status"],
                "calls": result["stage"]["usage"].get("calls"),
                "wall_seconds": result["wall_seconds"],
            }
        ),
        flush=True,
    )
    return result
