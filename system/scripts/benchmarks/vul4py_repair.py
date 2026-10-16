"""Known-location Vul4Py repair benchmark through the production Repair2 workflow."""

import argparse
import json
import shutil
import subprocess
from pathlib import Path
from uuid import UUID, uuid4

from app.adapters.ai.policy import policy_snapshot
from app.adapters.artifacts import ArtifactStore
from app.adapters.snapshot import snapshot_digest
from app.core.audit_config import audit_settings
from app.core.db import engine
from app.domain.audit import AuditError
from app.models import User
from app.persistence.audit_models import AuditRun
from app.persistence.stage_models import Candidate, RepairRecord, StageRun
from app.services.evidence import EvidenceService
from app.services.repair import RepairService
from app.workflows.repair import build_repair_graph
from scripts.benchmarks.formal_runtime import checkpoint_stage
from scripts.benchmarks.realvuln_run import stage, verify_implementation
from scripts.benchmarks.vul4py_oracle import container, junit, test_pass
from scripts.benchmarks.vul4py_prepare import save
from sqlmodel import Session, select


def register(identity, output):
    receipt = output / "runs" / identity / "input.json"
    if receipt.exists():
        return json.loads(receipt.read_text())
    case = output / "workspaces" / identity
    source = case / "vulnerable"
    meta = json.loads((case / "meta.json").read_text())
    paths = [p for p in meta["new_code_files"] if (source / p).is_file()]
    if not paths or len(paths) > 30:
        raise RuntimeError(
            "Known target files missing or exceed production 30-file limit"
        )
    # Public intended-behaviour text, without reference patch or fixed source.
    message = subprocess.check_output(
        [
            "git",
            "-C",
            str(case / "evaluator-git"),
            "show",
            "-s",
            "--format=%B",
            meta["fix_commit"],
        ],
        text=True,
    ).strip()
    description = f"Known vulnerability {identity}. Repair the vulnerable implementation while retaining normal behaviour. Public change description: {message[:3000]}"
    audit_id, owner_id = uuid4(), uuid4()
    digest = snapshot_digest(source)
    with Session(engine) as db:
        db.add(
            User(
                id=owner_id,
                email=f"vul4py-{owner_id}@research.invalid",
                hashed_password="disabled-research",
                is_active=False,
            )
        )
        db.commit()
        audit = AuditRun(
            id=audit_id,
            owner_id=owner_id,
            source_run_id=audit_id,
            project_name=identity,
            language="python",
            status="ready",
            phase="known_vulnerability_repair_benchmark",
            snapshot_hash=digest,
            query_pack=audit_settings.PYTHON_QUERY_PACK,
            suite="not_scanned",
            coverage={"known_location_repair": True, "static_scan_not_run": True},
        )
        db.add(audit)
        db.commit()
        target_stage = StageRun(
            audit_id=audit_id, kind="benchmark_target", status="completed"
        )
        db.add(target_stage)
        db.commit()
        db.refresh(target_stage)
        target_id = target_stage.id
    directory = ArtifactStore().directory(str(audit_id))
    (directory / "source").symlink_to(source, target_is_directory=True)
    evidence = EvidenceService(str(audit_id), str(target_id), []).read(paths[0], 1, 100)
    with Session(engine) as db:
        candidate = Candidate(
            audit_id=audit_id,
            stage_id=target_id,
            origin="benchmark_known_location",
            status="confirmed",
            title=identity,
            description=description,
            weakness="unknown",
            location={"file": paths[0], "line": 1},
            evidence_ids=[evidence["id"]],
        )
        db.add(candidate)
        db.commit()
        db.refresh(candidate)
        candidate_id = str(candidate.id)
    result = {
        "audit_id": str(audit_id),
        "candidate_id": candidate_id,
        "allowed_paths": paths,
        "snapshot": digest,
        "input_regime": "known target files from metadata + public commit message; no fixed code/diff/tests; not blind discovery or human confirmation",
    }
    save(receipt, result)
    return result


def evaluate_candidate(identity, record, output, image):
    case = output / "evaluator" / identity
    stage_root = ArtifactStore().directory(str(record.stage_id))
    attempts = record.validation.get("semantic_scope", {}).get("attempts")
    workspace = stage_root / f"attempt-{attempts}" / "workspace"
    if not workspace.exists():
        return {
            "status": "repair_failed",
            "reason": "no_applied_workspace",
            "joint_pass": False,
        }
    candidate = case / "candidate"
    if candidate.exists():
        raise RuntimeError(
            "Candidate evaluator workspace already exists without receipt"
        )
    shutil.copytree(workspace, candidate, symlinks=True)
    patch = stage_root / f"attempt-{attempts}" / "repair.diff"
    if patch.exists():
        shutil.copyfile(patch, output / "runs" / identity / "patch.diff")
    setup = container(case, output, "setup", image, ["candidate"])
    if setup["status"] != "succeeded":
        return {"status": "environment_failed", "setup": setup, "joint_pass": False}
    checks = container(case, output, "tests", image, ["candidate"])
    if checks["status"] != "succeeded":
        return {
            "status": "environment_failed",
            "execution": checks,
            "joint_pass": False,
        }
    result = json.loads((case / "tests-result.json").read_text())["candidate"]
    reports = {
        kind: junit(case / "logs" / f"{kind}_candidate.junit.xml")
        for kind in ("functional", "exploit")
    }
    functional = test_pass(result["functional_rc"], reports["functional"])
    security = test_pass(result["exploit_rc"], reports["exploit"])
    return {
        "status": "evaluated",
        "joint_pass": functional and security,
        "functional_pass": functional,
        "security_pass": security,
        "results": result,
        "junit": reports,
        "human_correct": None,
        "setup": setup,
        "execution": checks,
    }


def run(identity, output, policy, image):
    receipt = output / "runs" / identity / "result.json"
    if receipt.exists():
        return json.loads(receipt.read_text())
    calibration = json.loads(
        (output / "calibration" / identity / "result.json").read_text()
    )
    result = {
        "vuln_id": identity,
        "status": "not_evaluated",
        "joint_pass": False,
        "human_correct": None,
        "oracle_eligible": calibration["accepted"],
    }
    config = json.loads((output / "repair-config.json").read_text())
    if not calibration["accepted"] and not config.get("generate_uncalibrated", False):
        result["reason"] = "oracle_not_calibrated"
    else:
        try:
            verify_implementation(output)
            inputs = register(identity, output)
            generation = checkpoint_stage(
                output / "runs" / identity / "generation.json",
                lambda: stage(
                    inputs["audit_id"],
                    "repair",
                    json.loads((output / "repair-config.json").read_text()).get(
                        "prompt_version", "2"
                    ),
                    {
                        "candidate_ids": [inputs["candidate_id"]],
                        "allowed_paths": inputs["allowed_paths"],
                        "validation_profile": "syntax",
                        "rescan": False,
                        **(
                            {
                                "verification_suite_id": json.loads(
                                    (output / "repair-config.json").read_text()
                                )["verification_suite_ids"][identity]
                            }
                            if identity
                            in json.loads(
                                (output / "repair-config.json").read_text()
                            ).get("verification_suite_ids", {})
                            else {}
                        ),
                    },
                    policy,
                ),
                RepairService,
                build_repair_graph,
            )
            result.update(
                stage_id=generation["stage_id"],
                stage_status=generation["stage"]["status"],
                usage=generation["stage"]["usage"],
            )
            with Session(engine) as db:
                record = db.exec(
                    select(RepairRecord).where(
                        RepairRecord.stage_id == UUID(generation["stage_id"])
                    )
                ).first()
            if record and calibration["accepted"]:
                result.update(evaluate_candidate(identity, record, output, image))
            elif record:
                # Exercise production repair for performance only. An invalid
                # baseline cannot support a security or functional score.
                attempt = record.validation.get("semantic_scope", {}).get("attempts")
                workspace = (
                    ArtifactStore().directory(str(record.stage_id))
                    / f"attempt-{attempt}"
                    / "workspace"
                )
                result.update(
                    status="generated_unscored"
                    if workspace.exists()
                    else "repair_failed",
                    reason="oracle_not_calibrated"
                    if workspace.exists()
                    else "no_applied_workspace",
                    security_pass=None,
                    functional_pass=None,
                )
            else:
                result.update(
                    status="repair_failed",
                    reason=generation["stage"].get("error") or "no_repair_record",
                )
            verify_implementation(output)
        except (OSError, RuntimeError, ValueError, AuditError) as error:
            result.update(status="repair_failed", reason=str(error))
    save(receipt, result)
    print(identity, result["status"], "joint_pass", result["joint_pass"], flush=True)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--projects", nargs="+")
    parser.add_argument("--initialize-only", action="store_true")
    parser.add_argument("--generate-uncalibrated", action="store_true")
    parser.add_argument("--prompt-version", choices=["2", "3"], default="3")
    args = parser.parse_args()
    output = args.output.resolve()
    policy = policy_snapshot("repair")
    policy.update(max_calls=0, max_tokens=0, max_seconds=0)
    policy["execution_mode"] = "progress_with_local_repair_attempt_and_tool_limits"
    image = json.loads((output / "oracle-config.json").read_text())["image_id"]
    config = {
        "policy": policy,
        "prompt_version": args.prompt_version,
        "input_regime": "known-location repair",
        "static_scan_not_run": True,
        "human_review_not_performed": True,
        "image_id": image,
    }
    if args.generate_uncalibrated:
        config["generate_uncalibrated"] = True
    if (output / "repair-config.json").exists() and json.loads(
        (output / "repair-config.json").read_text()
    ) != config:
        raise RuntimeError("Frozen repair configuration changed")
    save(output / "repair-config.json", config)
    if args.initialize_only:
        return
    ids = [
        r["vuln_id"]
        for r in json.loads((output / "manifest.json").read_text())["cases"]
    ]
    if args.projects:
        if not set(args.projects) <= set(ids):
            raise RuntimeError("Unknown task ID")
        ids = args.projects
    rows = [run(identity, output, policy, image) for identity in ids]
    save(
        output / "repair-summary.json",
        {
            "cases": rows,
            "attempted": len(rows),
            "total_frozen": 100,
            "joint_pass": sum(r["joint_pass"] for r in rows),
            "human_correct": None,
        },
    )


if __name__ == "__main__":
    main()
