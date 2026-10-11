"""Paired K/v6 comparison on the six original tasks and exact hidden fixtures."""

import argparse
import copy
import json
import logging
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from uuid import UUID

from app.adapters.ai.provider import CompatibleModel
from app.core.db import engine
from app.domain.audit import AuditError
from app.persistence.knowledge_models import RuleVersion
from app.persistence.stage_models import StageRun
from app.persistence.stage_repository import StageRepository
from app.services.context_materials import save_json
from app.services.rules import RuleService
from sqlmodel import Session, select

from scripts.benchmarks.legacy_rag_dataset import (
    ROOT,
    freeze,
    historical_row,
    prepare_case,
    reference_manifest,
    verify_frozen,
)
from scripts.benchmarks.legacy_rag_scoring import observed, publish_report, score


def run_one(output, manifest, case, arm, number):
    path = output / "records" / f"{case['id']}-{arm}-{number}.json"
    if path.exists():
        return json.loads(path.read_text())
    old = historical_row(output, case["id"], number)
    inputs = {
        **old["stage"]["inputs"],
        "source_paths": manifest["audits"][case["id"]]["source_paths"],
    }
    policy = copy.deepcopy(manifest["policy"])
    policy["rule_experiment"] = (
        {"routing": True, "full_feedback": True, "spec": True, "execute_dev": True}
        if arm == "old_K"
        else {
            **manifest.get("arm_experiments", {}).get(arm, {}),
            "retrieval_mode": manifest.get("arm_experiments", {})
            .get(arm, {})
            .get("retrieval_mode", manifest.get("new_retrieval_mode", "auto")),
            "collection_routing": True,
            "corpus_document_ids": manifest["corpus_document_ids"],
        }
    )
    version = "3" if arm == "old_K" else manifest.get("arm_versions", {}).get(arm, "6")
    marker = output / "started" / path.name
    if marker.exists():
        raise RuntimeError(
            "A previous call has no completed record; retain its stage, do not silently repeat it"
        )
    with Session(engine) as db:
        stage = StageRun(
            audit_id=UUID(manifest["audits"][case["id"]]["id"]),
            kind="rule",
            inputs=inputs,
            prompt_version=version,
            model_config_snapshot=policy,
        )
        db.add(stage)
        db.commit()
        db.refresh(stage)
        identifier = str(stage.id)
    save_json(
        marker,
        {"stage_id": identifier, "arm": arm, "case": case["id"], "round": number},
    )
    repo = StageRepository()
    repo.claim(identifier)
    provider = CompatibleModel()
    provider.bind_stage(identifier, version)
    service = RuleService(identifier, provider)
    start = time.perf_counter()
    error = None
    try:
        if arm == "old_K":
            # Exact historical routed retrieval output, not today's enlarged public corpus.
            knowledge = copy.deepcopy(old["stage"]["result"]["retrieval"])
            save_json(service.directory / "benchmark-frozen-retrieval.json", knowledge)
            repo.update(
                identifier,
                phase="frozen_historical_retrieval",
                result={"retrieval": knowledge},
            )
            state = {"knowledge": knowledge, "target": None}
        else:
            state = service.retrieve()
        generated = service.generate(state)
        repo.update(
            identifier,
            status="completed",
            phase="benchmark_generation_finished",
            result={
                **repo.get(identifier).result,
                "benchmark_rule_id": generated["rule_id"],
            },
        )
    except (AuditError, OSError, ValueError) as exc:
        error = {
            "type": type(exc).__name__,
            "code": getattr(exc, "code", "unknown"),
            "message": str(exc)[:1200],
        }
        repo.update(
            identifier,
            status="failed",
            phase="benchmark_generation_failed",
            error=error["message"],
        )
    with Session(engine) as db:
        stage = db.get(StageRun, UUID(identifier))
        rules = db.exec(
            select(RuleVersion).where(RuleVersion.stage_id == UUID(identifier))
        ).all()
        row = {
            "arm": arm,
            "case": case["id"],
            "round": number,
            "generation_seconds": time.perf_counter() - start,
            "error": error,
            "stage": stage.model_dump(mode="json"),
            "rules": [r.model_dump(mode="json") for r in rules],
            **observed(identifier),
        }
    # Persist generation before evaluation; its failures are not regenerated.
    save_json(output / "generation" / path.name, row)
    row = score(output, row)
    save_json(path, row)
    print(
        json.dumps(
            {
                "arm": arm,
                "case": case["id"],
                "round": number,
                "generated": bool(row["rules"]),
                "hidden": row["oracle"]["status"],
                "seconds": round(row["generation_seconds"], 2),
                "error": error,
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "artifacts/benchmarks/legacy-rag-matched-20261004",
    )
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--reference-run",
        type=Path,
        help="Reuse all 18 old controls and audits from a completed run; execute only new auto requests",
    )
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() and not args.resume:
        raise RuntimeError("Output exists; use --resume to preserve completed requests")
    output.mkdir(parents=True, exist_ok=True)
    (output / "records").mkdir(exist_ok=True)
    logging.basicConfig(filename=output / "execution.log", level=logging.WARNING)
    if args.resume:
        manifest = json.loads((output / "manifest.json").read_text())
    elif args.reference_run:
        manifest = reference_manifest(output, args.reference_run.resolve())
    else:
        manifest = freeze(output, 3)
    verify_frozen(output, manifest)
    print("OUTPUT=" + str(output), flush=True)
    # Baseline setup is deterministic and never provides hidden variants to generation.
    for case in manifest["cases"]:
        if case["id"] not in manifest["audits"]:
            manifest["audits"][case["id"]] = prepare_case(output, manifest, case)
            save_json(output / "manifest.json", manifest)
            print("PREPARED=" + case["id"], flush=True)
    rng = random.Random(manifest["seed"])
    cases = list(manifest["cases"])
    rng.shuffle(cases)

    def run_case(index, case):
        # A case is handled by one worker, so its original/hidden DB is never concurrent.
        randomizer = random.Random(manifest["seed"] + index)
        for number in range(1, 4):
            arms = ["old_K", "new_v6"]
            randomizer.shuffle(arms)
            for arm in arms:
                run_one(output, manifest, case, arm, number)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run_case, i, case) for i, case in enumerate(cases)]
        for future in as_completed(futures):
            future.result()
            report = publish_report(output, manifest)
            print(
                "PARTIAL=" + json.dumps(report["groups"], ensure_ascii=False),
                flush=True,
            )
    verify_frozen(output, manifest)
    report = publish_report(output, manifest)
    print("REPORT=" + str(output / "report.json"), flush=True)
    print(json.dumps(report["groups"], ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
