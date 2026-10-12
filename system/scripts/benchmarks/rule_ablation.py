"""Preregistered paired real-model ablations; isolated owner, no auto approval."""

import argparse
import hashlib
import json
import logging
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from uuid import UUID, uuid4

from sqlmodel import Session, select
from app.adapters.ai.policy import policy_snapshot
from app.adapters.codeql.custom import compile_query, fixed_dependencies, prepare_query
from app.adapters.codeql.rule_spec import detector_template
from app.core.db import engine
from app.jobs.stages import execute_stage
from app.models import User
from app.persistence.audit_models import AuditRun
from app.persistence.knowledge_models import KnowledgeChunk, RuleVersion
from app.persistence.stage_models import StageRun
from app.services.rule_holdouts import catalog
from scripts.benchmarks.rule_ablation_oracles import (
    build_databases,
    evaluate,
    variant_dataset,
)

ROOT = Path(__file__).resolve().parents[3]
ARMS = {
    "A_bm25_log": {"routing": False, "full_feedback": False},
    "B_routed_log": {"routing": True, "full_feedback": False},
    "C_bm25_candidate": {"routing": False, "full_feedback": True},
    "D_routed_candidate": {"routing": True, "full_feedback": True},
    "E_spec_bm25": {"routing": False, "full_feedback": True, "spec": True},
    "F_spec_routed": {"routing": True, "full_feedback": True, "spec": True},
    "G_routed_candidate_lsp": {"routing": True, "full_feedback": True, "lsp": True},
}


def initialize(output):
    reference = json.loads(
        next(
            (ROOT / "artifacts/benchmarks").glob("library-control-*/report.json")
        ).read_text()
    )
    owner = uuid4()
    with Session(engine) as db:
        previous = db.get(AuditRun, UUID(reference["stages"][0]["stage"]["audit_id"]))
        db.add(
            User(
                id=owner,
                email=f"{owner}@benchmark.invalid",
                hashed_password="disabled-research-owner",
                is_active=False,
            )
        )
        db.commit()
        corpus = db.exec(
            select(KnowledgeChunk).where(
                (KnowledgeChunk.owner_id == previous.owner_id)
                | KnowledgeChunk.owner_id.is_(None)
            )
        ).all()
        frozen = [row.model_dump(mode="json", exclude={"embedding"}) for row in corpus]
        for row in corpus:
            if row.owner_id is not None:
                db.add(
                    KnowledgeChunk(
                        **{
                            **row.model_dump(exclude={"id", "created_at"}),
                            "owner_id": owner,
                        }
                    )
                )
        db.commit()
        # Reuse completed immutable source snapshots/baseline records without rescanning.
        base = json.loads(
            next(
                (ROOT / "artifacts/benchmarks").glob("phase-one-*/report.json")
            ).read_text()
        )
        audits = {}
        for language in ("python", "javascript"):
            stage = next(
                row
                for row in base["stages"]
                if row["case"].startswith(language + "-eval-")
            )["stage"]
            old = db.get(AuditRun, UUID(stage["audit_id"]))
            fresh = AuditRun(
                **{
                    **old.model_dump(exclude={"id", "created_at", "updated_at"}),
                    "owner_id": owner,
                    "source_run_id": old.source_run_id or old.id,
                }
            )
            db.add(fresh)
            db.commit()
            db.refresh(fresh)
            audits[language] = str(fresh.id)
    (output / "corpus.json").write_text(
        json.dumps(frozen, ensure_ascii=False, indent=2)
    )
    return audits, hashlib.sha256(
        json.dumps(frozen, sort_keys=True).encode()
    ).hexdigest()


def run_one(output, audit_id, data, arm, round_number, policy):
    frozen_policy = {**policy, "rule_experiment": ARMS[arm]}
    operation = data["operation"]
    requirement = f"Generate a fixed-version CodeQL vulnerability_detector for {data['language']} {operation}. Cite retrieved API sources and explain baseline coverage limitations. Detect external user input flowing to the actual dangerous operation, including aliases. Exclude safe constants, shadowed functions and sanitized/parameterized operations. Include small positive and negative regression fixtures. Do not claim new coverage when reusing an official detector."
    with Session(engine) as db:
        stage = StageRun(
            audit_id=UUID(audit_id),
            kind="rule",
            inputs={
                "requirement": requirement,
                "purpose": "vulnerability_detector",
                "strategy": "new_query",
                "holdout_id": data["id"],
            },
            prompt_version="3",
            model_config_snapshot=frozen_policy,
        )
        db.add(stage)
        db.commit()
        db.refresh(stage)
        identifier = stage.id
    start = time.perf_counter()
    execute_stage.run(str(identifier))
    with Session(engine) as db:
        stage = db.get(StageRun, identifier)
        rules = db.exec(
            select(RuleVersion).where(RuleVersion.stage_id == identifier)
        ).all()
        row = {
            "arm": arm,
            "case": data["id"],
            "round": round_number,
            "generation_seconds": time.perf_counter() - start,
            "stage": stage.model_dump(mode="json"),
            "rules": [rule.model_dump(mode="json") for rule in rules],
        }
    (output / "records" / f"{identifier}.json").write_text(
        json.dumps(row, ensure_ascii=False, indent=2)
    )
    print(arm, data["id"], round_number, stage.status, flush=True)
    return row


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--resume", type=Path)
    parser.add_argument(
        "--arms",
        nargs="+",
        default=[key for key in ARMS if key != "G_routed_candidate_lsp"],
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.CRITICAL)
    output = args.resume or ROOT / "artifacts/benchmarks" / (
        "rule-ablation-" + str(uuid4())
    )
    if not args.resume:
        output.mkdir()
        (output / "records").mkdir()
        audits, corpus_hash = initialize(output)
        cases = [
            entry for entry in catalog() if entry["purpose"] == "vulnerability_detector"
        ]
        policy = policy_snapshot()
        policy["thinking_mode"] = "disabled"
        policy["budgets"]["rule"] = 6000
        manifest = {
            "arms": {key: ARMS[key] for key in args.arms},
            "rounds": args.rounds,
            "workers": args.workers,
            "audits": audits,
            "corpus_hash": corpus_hash,
            "policy": policy,
            "cases": cases,
            "scope": "6 semantic tasks, 3 repeats; not 18 independent tasks. Spec reuses official templates; evaluator-only renamed/offset variants. No auto fixture approval/publication.",
            "seed": 20261003,
        }
        (output / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2)
        )
    else:
        manifest = json.loads((output / "manifest.json").read_text())
        audits = manifest["audits"]
        policy = manifest["policy"]
        cases = manifest["cases"]
    print("OUTPUT=" + str(output), flush=True)
    existing = [
        json.loads(path.read_text()) for path in (output / "records").glob("*.json")
    ]
    done = {(row["arm"], row["case"], row["round"]) for row in existing}
    tasks = [
        (case, arm, round_number)
        for round_number in range(1, manifest["rounds"] + 1)
        for case in cases
        for arm in manifest["arms"]
        if (arm, case["id"], round_number) not in done
    ]
    random.Random(manifest["seed"]).shuffle(tasks)
    with ThreadPoolExecutor(max_workers=manifest["workers"]) as pool:
        futures = [
            pool.submit(
                run_one, output, audits[case["language"]], case, arm, number, policy
            )
            for case, arm, number in tasks
        ]
        for future in as_completed(futures):
            future.result()
    # Only after generation: evaluator-only data remains outside generation graph.
    holdouts = {case["id"]: variant_dataset(case["id"]) for case in cases}
    for key, data in holdouts.items():
        directory = output / "holdouts" / key
        (directory).mkdir(parents=True, exist_ok=True)
        (directory / "dataset.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2)
        )
        if not (directory / "negative-database").exists():
            build_databases(directory, data)
    baseline = []
    for key, data in holdouts.items():
        pack = output / "baseline" / key
        query, provenance = detector_template(data["language"], data["operation"])
        prepare_query(
            pack, data["language"], query, {}, fixed_dependencies(data["language"])
        )
        compile_query(pack, pack / "compile.log")
        start = time.perf_counter()
        result = evaluate(output / "holdouts" / key, pack, data, pack / "oracle")
        baseline.append(
            {
                "case": key,
                "result": result,
                "provenance": provenance,
                "evaluation_seconds": time.perf_counter() - start,
            }
        )
        (output / "baseline.json").write_text(
            json.dumps(baseline, ensure_ascii=False, indent=2)
        )
    records = [
        json.loads(path.read_text()) for path in (output / "records").glob("*.json")
    ]
    for row in records:
        if row.get("oracle") or row.get("oracle_error"):
            continue
        if not row["rules"]:
            row["oracle"] = {"status": "not_generated"}
        else:
            rule = row["rules"][0]
            pack = output / "evaluation" / row["stage"]["id"] / "pack"
            start = time.perf_counter()
            try:
                prepare_query(
                    pack,
                    rule["language"],
                    rule["query"],
                    rule["modules"],
                    rule["dependencies"],
                )
                row["oracle"] = evaluate(
                    output / "holdouts" / row["case"],
                    pack,
                    holdouts[row["case"]],
                    pack.parent / "oracle",
                )
            except Exception as exc:
                row["oracle_error"] = {"type": type(exc).__name__, "message": str(exc)}
            row["evaluation_seconds"] = time.perf_counter() - start
        (output / "records" / f"{row['stage']['id']}.json").write_text(
            json.dumps(row, ensure_ascii=False, indent=2)
        )
        print(
            "ORACLE",
            row["arm"],
            row["case"],
            row.get("oracle", {}).get("status", "error"),
            flush=True,
        )
    (output / "report.json").write_text(
        json.dumps(
            {"manifest": manifest, "baseline": baseline, "records": records},
            ensure_ascii=False,
            indent=2,
        )
    )
    print("REPORT=" + str(output / "report.json"), flush=True)


if __name__ == "__main__":
    main()
