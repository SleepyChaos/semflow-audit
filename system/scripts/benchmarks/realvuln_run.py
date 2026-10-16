"""Run frozen production CodeQL, scout v7 and review v12 on every paper target."""

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from uuid import UUID

from app.adapters.ai.policy import policy_snapshot
from app.adapters.codeql.sarif import parse_sarif
from app.adapters.codeql.scanner import CodeQLScanner
from app.adapters.snapshot import snapshot_digest
from app.contracts.scouting import ScoutRequest
from app.contracts.stages import ReviewRequest
from app.core.audit_config import audit_settings
from app.core.db import engine
from app.domain.audit import ScanPlan
from app.persistence.stage_models import StageRun
from app.services.review import ReviewService
from app.services.scouting import ScoutService
from app.workflows.review import build_review_graph
from app.workflows.scouting import build_scout_graph
from scripts.benchmarks.formal_baseline import run_one
from scripts.benchmarks.formal_runtime import checkpoint_stage, register_audit
from scripts.benchmarks.realvuln_prepare import save
from sqlmodel import Session


def read(path):
    return json.loads(path.read_text())


def verify_implementation(output):
    from scripts.benchmarks.benchmark_integrity import implementation_hashes

    frozen = output / "implementation"
    actual = implementation_hashes(frozen)
    if actual != read(output / "implementation-hashes.json"):
        raise RuntimeError("Frozen implementation changed")
    import app

    if not Path(app.__file__).resolve().is_relative_to(frozen):
        raise RuntimeError("Runner must import the frozen app through PYTHONPATH")


def stage(audit, kind, version, inputs, policy, result=None):
    with Session(engine) as db:
        item = StageRun(
            audit_id=UUID(audit),
            kind=kind,
            prompt_version=version,
            inputs=inputs,
            model_config_snapshot=policy,
            result=result or {},
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        return str(item.id)


def static_result(row, output, config):
    if config.get("reuse_static_from"):
        from scripts.benchmarks.realvuln_static_reuse import reuse_static

        return reuse_static(row, output, config)
    prior = output / "attempts/00-environment-path-error/static" / row["id"]
    directory = output / "static" / row["id"]
    if (directory / "result.json").exists():
        return read(directory / "result.json")
    if not (prior / "database/codeql-database.yml").is_file():
        return run_one(row, config, 1, output=output)
    old = read(prior / "result.json")
    if old["snapshot"] != snapshot_digest(Path(row["source"])):
        raise RuntimeError("Cannot reuse a database for changed source")
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "database").symlink_to(prior / "database", target_is_directory=True)
    pack = config["packs"]["python"]
    began = time.perf_counter()
    result = {
        **old,
        "rounds": [],
        "database_reused_from": str(prior),
        "status": "running",
        "prior_failed_attempt_retained": True,
    }
    try:
        sarif = directory / "round-1.sarif"
        CodeQLScanner().analyze(
            directory / "database",
            sarif,
            directory / "execution.log",
            ScanPlan("python", pack["pack"], pack["suite"]),
        )
        findings = parse_sarif(sarif, row["snapshot"])
        result.update(status="succeeded", error=None, error_type=None)
        result["rounds"] = [
            {
                "round": 1,
                "query_seconds": time.perf_counter() - began,
                "alerts": len(findings),
                "findings": findings,
            }
        ]
    except Exception as exc:  # noqa: BLE001 - persist external scan failure
        result.update(
            status="failed", error_type=type(exc).__name__, error=str(exc)[:1000]
        )
    result["wall_seconds"] = old.get("extract_seconds", 0) + time.perf_counter() - began
    save(directory / "result.json", result)
    print(
        json.dumps(
            {
                "project_id": row["id"],
                "static_status": result["status"],
                "alerts": len(result["rounds"][0]["findings"])
                if result["rounds"]
                else None,
            }
        ),
        flush=True,
    )
    return result


def audit_project(row, output, config):
    directory = output / "system" / row["id"]
    final = directory / "result.json"
    if final.exists():
        return read(final)
    verify_implementation(output)
    if snapshot_digest(Path(row["source"])) != row["snapshot"]:
        raise RuntimeError("Input changed before scan")
    static = static_result(row, output, config)
    static["scope"] = "all 26 frozen paper targets; real production CodeQL suite"
    save(output / "static" / row["id"] / "result.json", static)
    result = {
        "project_id": row["id"],
        "static_status": static["status"],
        "static_seconds": static["wall_seconds"],
        "status": "not_started",
    }
    if static["status"] != "succeeded":
        result.update(status="blocked_static_failure", error=static.get("error"))
        save(final, result)
        return result
    audit = register_audit(row["id"], output=output)
    result["audit_id"] = audit
    scout = checkpoint_stage(
        directory / "scout.json",
        lambda: stage(
            audit,
            "scout",
            "7",
            ScoutRequest().model_dump(mode="json"),
            config["model_policies"]["scout"],
        ),
        ScoutService,
        build_scout_graph,
    )
    review = checkpoint_stage(
        directory / "review.json",
        lambda: stage(
            audit,
            "review",
            "12",
            ReviewRequest().model_dump(mode="json"),
            config["model_policies"]["review"],
        ),
        ReviewService,
        build_review_graph,
    )
    coverage = scout["stage"]["result"].get("coverage", {})
    review_coverage = review["stage"]["result"].get("coverage_status")
    result.update(
        scout_stage_id=scout["stage_id"],
        review_stage_id=review["stage_id"],
        scout_status=scout["stage"]["status"],
        review_status=review["stage"]["status"],
        scout_coverage=coverage,
        review_coverage=review_coverage,
        scout_candidates=len(scout["candidates"]),
        supported_candidates=sum(
            c["model_assessment"] == "supported" for c in review["candidates"]
        ),
        excluded_candidates=sum(
            c["model_assessment"] == "excluded" for c in review["candidates"]
        ),
        unresolved_candidates=sum(
            c["model_assessment"] not in {"supported", "excluded"}
            for c in review["candidates"]
        ),
        scout_usage=scout["stage"]["usage"],
        review_usage=review["stage"]["usage"],
        scout_seconds=scout["wall_seconds"],
        review_seconds=review["wall_seconds"],
        sequential_chain_seconds=static["wall_seconds"]
        + scout["wall_seconds"]
        + review["wall_seconds"],
        timing_note="Static output shared across arms; sequential stage sum, not GUI concurrent latency",
        status="completed"
        if scout["stage"]["status"] == "completed"
        and review["stage"]["status"] == "completed"
        and coverage.get("status") == "completed"
        and review_coverage == "completed"
        else "partial",
    )
    verify_implementation(output)
    if snapshot_digest(Path(row["source"])) != row["snapshot"]:
        raise RuntimeError("Input changed during model audit")
    result["integrity_verified"] = True
    save(final, result)
    print(
        json.dumps(
            {
                k: result.get(k)
                for k in (
                    "project_id",
                    "status",
                    "scout_candidates",
                    "supported_candidates",
                    "excluded_candidates",
                    "unresolved_candidates",
                    "sequential_chain_seconds",
                )
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--projects", nargs="*")
    parser.add_argument("--reuse-static-from", type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    verify_implementation(output)
    config = {
        "codeql_cli": CodeQLScanner().version(),
        "packs": {
            "python": {
                "pack": audit_settings.PYTHON_QUERY_PACK,
                "suite": "codeql-suites/python-code-scanning.qls",
            }
        },
        "model_policies": {kind: policy_snapshot(kind) for kind in ("scout", "review")},
        "concurrency": args.concurrency,
        "scout_version": "7",
        "review_version": "12",
        "scout_inputs": ScoutRequest().model_dump(mode="json"),
        "review_inputs": ReviewRequest().model_dump(mode="json"),
        "selection": "all paper projects in frozen manifest order",
        "primary_system_output": "supported review candidates; unresolved exported separately",
        "secondary_system_output": "union minus validated exclusions; retain unresolved",
        "codeql_shared_once": True,
        "repair_and_rule_generation": "outside detection experiment",
        "runtime_paths": {
            "packs": str(audit_settings.CODEQL_PACK_PATH),
            "artifacts": str(audit_settings.ARTIFACT_ROOT),
        },
    }
    if args.reuse_static_from:
        config["reuse_static_from"] = str(args.reuse_static_from.resolve())
    if (output / "config.json").exists():
        if read(output / "config.json") != config:
            raise RuntimeError("Cannot resume with changed configuration")
    else:
        save(output / "config.json", config)
    targets = list(read(output / "dataset.json")["manifest"]["repos"])
    if args.projects:
        targets = [t for t in targets if t in args.projects]
    rows, submitted = [], set()
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = {}
        while len(submitted) < len(targets):
            for project in targets:
                receipt = output / "acquisition" / f"{project}.json"
                if project in submitted or not receipt.exists():
                    continue
                row = read(receipt)
                submitted.add(project)
                if row["status"] == "ready":
                    futures[pool.submit(audit_project, row, output, config)] = project
                else:
                    result = {
                        "project_id": project,
                        "status": "source_unavailable",
                        "static_status": "not_evaluated",
                        "error": row["attempts"],
                    }
                    save(output / "system" / project / "result.json", result)
                    rows.append(result)
            if len(submitted) < len(targets):
                time.sleep(3)
        for future in as_completed(futures):
            project = futures[future]
            try:
                rows.append(future.result())
            except Exception as exc:  # noqa: BLE001 - isolate a project failure
                result = {
                    "project_id": project,
                    "status": "runner_error",
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:1000],
                }
                save(output / "system" / project / "runner-error.json", result)
                rows.append(result)
                print(json.dumps(result), flush=True)
            save(
                output / "run-summary.json",
                {"projects": rows, "total_targets": len(targets)},
            )
    print(json.dumps({"finished": len(rows), "total": len(targets)}), flush=True)


if __name__ == "__main__":
    main()
