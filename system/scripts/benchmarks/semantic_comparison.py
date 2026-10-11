"""Compare historical defaults with semantic repair/dual-corpus rules using real IO.

Local microcases measure a limited development result, never population accuracy.
Evaluation files are added only to a separate copy AFTER generation. Production
repair validation keeps the existing syntax preset; no exploit replay is added.
"""

import argparse
import json
import logging
import shutil
import time
from pathlib import Path
from uuid import UUID, uuid4

import live_model as baseline
from app.adapters.ai.provider import CompatibleModel
from app.adapters.artifacts import ArtifactStore
from app.adapters.codeql.custom import validate_fixtures
from app.adapters.repair.validator import validate_workspace
from app.core.audit_config import audit_settings
from app.core.db import engine
from app.domain.audit import AuditError
from app.jobs.stages import execute_stage
from app.models import User
from app.persistence.knowledge_models import RuleVersion
from app.persistence.stage_models import Candidate, RepairRecord, StageRun
from app.services.evidence import EvidenceService
from app.services.rules import RuleService
from semantic_cases import CASES, RULE_CASES
from sqlmodel import Session, select

ROOT = baseline.ROOT
EXPERIMENT = {}


def target(audit_id, case):
    with Session(engine) as db:
        stage = StageRun(
            audit_id=audit_id, kind="comparison_confirmation", status="completed"
        )
        db.add(stage)
        db.commit()
        db.refresh(stage)
        stage_id = stage.id
    evidence = EvidenceService(str(audit_id), str(stage_id), []).read(
        case["file"], 1, 80
    )
    with Session(engine) as db:
        row = Candidate(
            audit_id=audit_id,
            stage_id=stage_id,
            origin="development_comparison",
            status="confirmed",
            title="Development target " + case["cwe"],
            description=case["description"],
            weakness=case["cwe"],
            location={"file": case["file"], "line": case["line"]},
            evidence_ids=[evidence["id"]],
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.id


def stage(audit_id, kind, version, inputs):
    with Session(engine) as db:
        from app.adapters.ai.policy import policy_snapshot

        row = StageRun(
            audit_id=audit_id,
            kind=kind,
            prompt_version=version,
            inputs=inputs,
            model_config_snapshot={**policy_snapshot(), "rule_experiment": EXPERIMENT}
            if kind == "rule"
            else {},
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.id


def compare_repair(audit_id, candidate, case, version, directory):
    identifier = stage(
        audit_id,
        "repair",
        version,
        {
            "candidate_ids": [str(candidate)],
            "allowed_paths": [case["file"]],
            "rescan": False,
            "validation_profile": "syntax",
        },
    )
    start = time.perf_counter()
    execute_stage.run(str(identifier))
    with Session(engine) as db:
        run = db.get(StageRun, identifier)
        record = db.exec(
            select(RepairRecord).where(RepairRecord.stage_id == identifier)
        ).first()
    row = {
        "stage_id": str(identifier),
        "version": version,
        "status": run.status,
        "error": run.error,
        "seconds": time.perf_counter() - start,
        "usage": run.usage,
        "model_calls": run.model_calls,
        "functional": {"status": "not_run"},
        "checks": record.validation if record else {},
    }
    if record:
        artifact = ArtifactStore().directory(str(identifier))
        workspace = (
            artifact / "workspace"
            if version == "1"
            else artifact
            / f"attempt-{record.validation['semantic_scope']['attempts']}/workspace"
        )
        if workspace.is_dir():
            evaluation = directory / str(identifier) / "evaluation"
            shutil.copytree(workspace, evaluation)
            (evaluation / "test_business.py").write_text(case["functional_test"])
            row["functional"] = validate_workspace(
                evaluation, "python", "python_pytest"
            )
            row["applied"] = True
    return row


def compare_rule(audit_id, candidate, case, version, directory):
    identifier = stage(
        audit_id,
        "rule",
        version,
        {
            "candidate_id": str(candidate),
            "requirement": case["requirement"],
            "purpose": "vulnerability_detector",
            "strategy": "auto",
        },
    )
    from app.persistence.stage_repository import StageRepository

    repository = StageRepository()
    repository.claim(str(identifier))
    provider = CompatibleModel()
    provider.bind_stage(str(identifier), version)
    service = RuleService(str(identifier), provider)
    start = time.perf_counter()
    row = {
        "stage_id": str(identifier),
        "version": version,
        "status": "failed",
        "compiled": False,
        "independent": {"status": "not_run"},
        "error": None,
    }
    try:
        generated = service.generate(service.retrieve())
        with Session(engine) as db:
            rule = db.get(RuleVersion, UUID(generated["rule_id"]))
        pack = service.directory / f"draft-{rule.validation['attempts'] - 1}"
        row.update(
            {
                "status": "draft",
                "compiled": True,
                "rule_id": str(rule.id),
                "development": rule.validation.get("development"),
                "project_replay": rule.validation.get("project_replay"),
            }
        )
        # Hidden to the generator; this result is not fed back or auto-published.
        row["independent"] = validate_fixtures(
            directory / str(identifier) / "evaluation", pack, "python", case["holdout"]
        )
    except (AuditError, OSError, ValueError) as exc:
        row["error"] = {
            "type": type(exc).__name__,
            "code": getattr(exc, "code", "unknown"),
            "message": str(exc)[:800],
        }
    timings = [
        json.loads(p.read_text())
        for p in (service.directory / "node-timings").glob("*.json")
    ]
    row["observed_compile_passed"] = any(
        t["node"] == "compile_draft" and t.get("candidate_passed") is True
        for t in timings
    )
    row["observed_development_passed"] = any(
        t["node"] == "execute_development" and t.get("candidate_passed") is True
        for t in timings
    )
    row.update(
        {
            "seconds": time.perf_counter() - start,
            "usage": provider.usage,
            "model_calls": provider.records,
        }
    )
    repository.update(
        str(identifier),
        status="completed" if row["status"] == "draft" else "failed",
        error=row["error"]["message"] if row["error"] else None,
        result={
            "comparison": {
                "compiled": row["compiled"],
                "independent": row["independent"]["status"],
            }
        },
    )
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--mode", choices=["repair", "rule", "both"], default="both")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--versions", default="")
    parser.add_argument(
        "--retrieval-mode", choices=["auto", "bm25", "vector", "hybrid"], default="auto"
    )
    parser.add_argument("--collection-routing", choices=["on", "off"], default="on")
    args = parser.parse_args()
    EXPERIMENT.update(
        {
            "retrieval_mode": args.retrieval_mode,
            "collection_routing": args.collection_routing == "on",
        }
    )
    output = args.output or ROOT / "artifacts/benchmarks" / (
        "semantic-comparison-" + str(uuid4())
    )
    output.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=output / "execution.log", level=logging.WARNING)
    owner = uuid4()
    with Session(engine) as db:
        db.add(
            User(
                id=owner,
                email=f"semantic-{owner}@research.invalid",
                hashed_password="disabled-comparison",
                is_active=False,
            )
        )
        db.commit()
    baseline.OUTPUT = output
    report = {
        "model": audit_settings.AI_MODEL,
        "rounds": args.rounds,
        "policy": {
            "thinking_mode": audit_settings.AI_THINKING_MODE,
            "rule_tokens": audit_settings.AI_RULE_TOKENS
            or audit_settings.AI_MAX_OUTPUT_TOKENS,
            "max_stage_tokens": audit_settings.AI_STAGE_MAX_TOKENS,
        },
        "owner": str(owner),
        "experiment": EXPERIMENT,
        "scope": "Development microcases. Frozen v1/v2 repairs, v2/v6 rules. Functional checks are evaluator-only. No population accuracy or exploit-replay claim.",
        "audits": [],
        "rows": [],
    }
    manifest = {"repair": CASES, "rule": RULE_CASES}
    for kind, cases in manifest.items():
        if args.mode not in {kind, "both"}:
            continue
        for name, case in cases.items():
            source = output / "sources" / name
            source.mkdir(parents=True, exist_ok=True)
            for path, text in case["files"].items():
                (source / path).write_text(text)
            audit_id, static_seconds = baseline.new_audit(owner, source, name, "python")
            candidate = target(audit_id, case)
            report["audits"].append(
                {"id": str(audit_id), "case": name, "static_seconds": static_seconds}
            )
            for number in range(1, args.rounds + 1):
                for version in (
                    args.versions.split(",")
                    if args.versions
                    else (["1", "2"] if kind == "repair" else ["2", "6"])
                ):
                    result = (compare_repair if kind == "repair" else compare_rule)(
                        audit_id, candidate, case, version, output
                    )
                    report["rows"].append(
                        {"kind": kind, "case": name, "round": number, **result}
                    )
                    (output / "report.json").write_text(
                        json.dumps(report, ensure_ascii=False, indent=2)
                    )
                    print(
                        json.dumps(
                            {
                                "kind": kind,
                                "case": name,
                                "round": number,
                                "version": version,
                                "status": result["status"],
                                "seconds": result["seconds"],
                                "evaluation": result.get(
                                    "functional", result.get("independent", {})
                                ).get("status"),
                                "error": result.get("error"),
                            },
                            ensure_ascii=False,
                        ),
                        flush=True,
                    )
    print("REPORT_PATH=" + str(output / "report.json"), flush=True)


if __name__ == "__main__":
    main()
