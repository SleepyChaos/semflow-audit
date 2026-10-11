"""Bounded real-provider benchmark; isolated owner, real graph/tools, no scripted AI.

Retains its disabled benchmark user's history for inspection. Generated rule
fixtures wait for evaluator approval; no generated rule is auto-published.
"""

import json
import logging
import shutil
import sys
import time
from pathlib import Path
from uuid import UUID, uuid4
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "system/backend"))
from app.adapters.artifacts import ArtifactStore
from app.adapters.codeql.sarif import parse_sarif
from app.adapters.codeql.scanner import CodeQLScanner
from app.core.audit_config import audit_settings
from app.core.db import engine
from app.domain.audit import ScanPlan
from app.jobs.stages import execute_stage
from app.models import User
from app.persistence.audit_models import AuditRun
from app.persistence.stage_models import Candidate, Decision, RepairRecord, StageRun
from app.services.evidence import EvidenceService
from app.services.uploads import create_run
from sqlmodel import Session, select


def new_audit(owner, source, label, language):
    archive = OUTPUT / (label + ".zip")
    with ZipFile(archive, "w") as bundle:
        for path in source.rglob("*"):
            if path.is_file():
                bundle.write(path, path.relative_to(source).as_posix())
    with Session(engine) as session:
        audit = create_run(
            session, owner, archive, "real-model-benchmark-" + label, language
        )
        identifier = audit.id
    directory = ArtifactStore().directory(str(identifier))
    scanner = CodeQLScanner()
    pack = (
        audit_settings.PYTHON_QUERY_PACK
        if language == "python"
        else audit_settings.JAVASCRIPT_QUERY_PACK
    )
    plan = ScanPlan(language, pack, f"codeql-suites/{language}-security-extended.qls")
    start = time.perf_counter()
    scanner.create_database(
        directory / "source", directory / "database", directory / "execution.log", plan
    )
    scanner.analyze(
        directory / "database",
        directory / "results.sarif",
        directory / "execution.log",
        plan,
    )
    with Session(engine) as session:
        audit = session.get(AuditRun, identifier)
        audit.status = audit.phase = "completed"
        audit.codeql_version = scanner.version()
        audit.findings = parse_sarif(directory / "results.sarif", audit.snapshot_hash)
        session.add(audit)
        session.commit()
    return identifier, time.perf_counter() - start


def run_stage(audit_id, kind, inputs, metadata):
    with Session(engine) as session:
        stage = StageRun(audit_id=audit_id, kind=kind, inputs=inputs)
        session.add(stage)
        session.commit()
        session.refresh(stage)
        identifier = stage.id
    start = time.perf_counter()
    execute_stage.run(str(identifier))
    with Session(engine) as session:
        stage = session.get(StageRun, identifier)
        record = {
            **metadata,
            "stage_id": str(identifier),
            "audit_id": str(audit_id),
            "kind": kind,
            "seconds": time.perf_counter() - start,
            "status": stage.status,
            "error": stage.error,
            "usage": stage.usage,
            "result": stage.result,
        }
        candidates = session.exec(
            select(Candidate).where(Candidate.stage_id == identifier)
        ).all()
        record["candidates"] = [row.model_dump(mode="json") for row in candidates]
        repair = session.exec(
            select(RepairRecord).where(RepairRecord.stage_id == identifier)
        ).first()
        if repair:
            record["repair"] = repair.model_dump(mode="json")
    REPORT["stages"].append(record)
    save()
    print(
        json.dumps(
            {
                k: record[k]
                for k in ["kind", "stage_id", "status", "seconds", "usage", "error"]
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    return record


def confirmed_target(audit_id, target):
    with Session(engine) as session:
        stage = StageRun(
            audit_id=audit_id,
            kind="benchmark_oracle_confirmation",
            status="completed",
            phase="independent_oracles_prevalidated",
        )
        session.add(stage)
        session.commit()
        session.refresh(stage)
        stage_id = stage.id
    evidence = EvidenceService(str(audit_id), str(stage_id), []).read(target, 1, 80)
    with Session(engine) as session:
        candidate = Candidate(
            audit_id=audit_id,
            stage_id=stage_id,
            origin="benchmark",
            title="Independently verified vulnerable fixture",
            description="Published security oracle failed on the vulnerable original and functional oracle passed. Preserve behavior and eliminate the root cause without changing tests.",
            status="confirmed",
            evidence_ids=[evidence["id"]],
            location={"file": target, "line": 1},
            identity_key="benchmark:" + str(audit_id),
        )
        session.add(candidate)
        session.commit()
        session.refresh(candidate)
        session.add(
            Decision(
                candidate_id=candidate.id,
                actor_id=OWNER,
                status="confirmed",
                reason="Research evaluator confirmed the published fixture using prior independent security and functional oracle results, not a production user decision.",
                evidence_ids=[evidence["id"]],
            )
        )
        session.commit()
        return candidate.id


def save():
    (OUTPUT / "report.json").write_text(
        json.dumps(REPORT, ensure_ascii=False, indent=2)
    )


def main():
    global OUTPUT, OWNER, REPORT
    OUTPUT = ROOT / "artifacts/benchmarks" / ("live-model-" + str(uuid4()))
    OUTPUT.mkdir(parents=True)
    OWNER = uuid4()
    REPORT = {
        "scope": "real-provider calibration, 3 rounds, isolated disabled research owner, no LLM-as-ground-truth",
        "model": audit_settings.AI_MODEL,
        "provider": "Volcengine Ark user-specified coding-plan endpoint",
        "owner": str(OWNER),
        "stages": [],
        "audits": [],
    }
    logging.basicConfig(filename=OUTPUT / "execution.log", level=logging.WARNING)
    with Session(engine) as session:
        session.add(
            User(
                id=OWNER,
                email=f"{OWNER}@benchmark.invalid",
                hashed_password="disabled-research-owner",
                is_active=False,
            )
        )
        session.commit()

    # Six bounded eval-review targets; shadowed JS also has separately scored XSS.
    heldout = next((ROOT / "artifacts/benchmarks").glob("rule-holdout-*/source"))
    py_source = OUTPUT / "python-review"
    py_source.mkdir()
    for name in ["direct.py", "constant.py", "shadowed_function.py"]:
        shutil.copyfile(heldout / name, py_source / name)
    js_source = OUTPUT / "javascript-review"
    js_source.mkdir()
    js_fixture = next(
        (ROOT / "artifacts/benchmarks").glob("e244*/javascript/source/eval_positive.js")
    )
    shutil.copyfile(js_fixture, js_source / "direct.js")
    (js_source / "constant.js").write_text(
        'const express=require("express");const app=express();app.get("/",(req,res)=>res.send(String(eval("1+2"))));\n'
    )
    (js_source / "shadowed.js").write_text(
        'const express=require("express");const app=express();function eval(value){return value;}app.get("/",(req,res)=>res.send(eval(req.query.value)));\n'
    )
    for language, source, names in [
        ("python", py_source, ["direct.py", "constant.py", "shadowed_function.py"]),
        ("javascript", js_source, ["direct.js", "constant.js", "shadowed.js"]),
    ]:
        audit_id, seconds = new_audit(OWNER, source, language + "-review", language)
        REPORT["audits"].append(
            {"id": str(audit_id), "language": language, "static_seconds": seconds}
        )
        save()
        for round_number in range(1, 4):
            for name in names:
                run_stage(
                    audit_id,
                    "review",
                    {
                        "paths": [name],
                        "discover": True,
                        "max_steps": 8,
                        "max_context_chars": 60000,
                    },
                    {
                        "case": name,
                        "round": round_number,
                        "expected_vulnerable": name.startswith("direct"),
                        "label_scope": "CWE-094/095 eval code execution only",
                    },
                )

    # Two independently calibrated published cases, each with actual model patching.
    external = next((ROOT / "artifacts/benchmarks").glob("external-oracles-*"))
    for language, label, target in [
        ("python", "python-sqli", "db.py"),
        ("javascript", "javascript-pp", "merge.js"),
    ]:
        source = external / label / "vulnerable"
        audit_id, seconds = new_audit(OWNER, source, label, language)
        REPORT["audits"].append(
            {"id": str(audit_id), "language": language, "static_seconds": seconds}
        )
        save()
        candidate_id = confirmed_target(audit_id, target)
        for round_number in range(1, 4):
            run_stage(
                audit_id,
                "repair",
                {
                    "candidate_ids": [str(candidate_id)],
                    "allowed_paths": [target],
                    "validation_profile": "python_pytest"
                    if language == "python"
                    else "javascript_test",
                    "rescan": True,
                },
                {"case": label, "round": round_number, "independent_oracle": True},
            )

    # Real RAG synthesis; fixtures remain awaiting evaluator inspection.
    audit_id = UUID(REPORT["audits"][0]["id"])
    for round_number in range(1, 4):
        run_stage(
            audit_id,
            "rule",
            {
                "requirement": "Python CodeQL eval 动态执行复审锚点规则；明确这不是污点漏洞证明。识别直接 eval 调用，给出可解析的正反例与精确位置，引用实际检索的知识和固定API。",
                "strategy": "new_query",
            },
            {
                "case": "python-eval-review-anchor",
                "round": round_number,
                "generated_fixture_approval": "pending_evaluator",
            },
        )
    print("REPORT_PATH=" + str(OUTPUT / "report.json"), flush=True)


if __name__ == "__main__":
    main()
