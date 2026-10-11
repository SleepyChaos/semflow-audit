"""Frozen v1/v2 real-model comparison with separate derived functional/security tests."""

import argparse
import json
import shutil
import subprocess
import time
from pathlib import Path
from uuid import UUID, uuid4

from app.adapters.artifacts import ArtifactStore
from app.adapters.codeql.scanner import CodeQLScanner
from app.core.audit_config import audit_settings
from app.core.db import engine
from app.persistence.stage_models import RepairRecord
from app.services.repair import RepairService
from app.workflows.repair import build_repair_graph
from sqlmodel import Session, select

from scripts.benchmarks.formal_baseline import run_one
from scripts.benchmarks.formal_runtime import checkpoint_stage, register_audit
from scripts.benchmarks.semantic_comparison import target
from scripts.benchmarks.supplemental_prepare import ROOT, save, sha
from scripts.benchmarks.supplemental_repair_cases import cases


def evaluate(directory, row, source):
    """Run each assertion family in a separate networkless, read-only container."""
    directory.mkdir(parents=True, exist_ok=True)
    source_name = row["file"]
    shutil.copyfile(source / source_name, directory / source_name)
    language = row["language"]
    image = (
        audit_settings.VALIDATOR_PYTHON_IMAGE
        if language == "python"
        else audit_settings.VALIDATOR_JS_IMAGE
    )
    image_id = subprocess.check_output(
        ["docker", "image", "inspect", "--format", "{{.Id}}", image], text=True
    ).strip()
    results = {
        "image": image_id,
        "oracle_origin": "derived-agent-authored-not-human-reviewed",
    }
    for kind in ("normal", "security"):
        name = f"check_{kind}." + ("py" if language == "python" else "js")
        (directory / name).write_text(row[kind])
        command = ["python", name] if language == "python" else ["node", name]
        container_name = "supplemental-oracle-" + uuid4().hex
        args = [
            "docker",
            "run",
            "--name",
            container_name,
            "--rm",
            "--pull=never",
            "--network=none",
            "--read-only",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--pids-limit=64",
            "--memory=256m",
            "--cpus=1",
            "--user=65534:65534",
            "--tmpfs=/tmp:rw,noexec,nosuid,size=32m",
            "--env=PYTHONDONTWRITEBYTECODE=1",
            "--workdir=/eval",
            "--mount",
            f"type=bind,src={directory.resolve()},dst=/eval,readonly",
            image_id,
            *command,
        ]
        started = time.perf_counter()
        try:
            result = subprocess.run(
                args, capture_output=True, text=True, timeout=45, check=False
            )
            results[kind] = {
                "status": "passed" if result.returncode == 0 else "failed",
                "exit_code": result.returncode,
                "seconds": time.perf_counter() - started,
            }
            (directory / f"{kind}.stdout.txt").write_text(result.stdout)
            (directory / f"{kind}.stderr.txt").write_text(result.stderr)
        except subprocess.TimeoutExpired:
            subprocess.run(
                ["docker", "rm", "-f", container_name],
                capture_output=True,
                timeout=15,
                check=False,
            )
            results[kind] = {
                "status": "timeout",
                "seconds": time.perf_counter() - started,
            }
    results["joint_pass"] = all(
        results[k]["status"] == "passed" for k in ("normal", "security")
    )
    save(directory / "oracle-result.json", results)
    return results


def prepare(output):
    if output.exists():
        raise RuntimeError("Never overwrite a repair freeze")
    dataset = cases()
    rows = []
    for row in dataset:
        source = output / "sources" / row["id"]
        source.mkdir(parents=True)
        (source / row["file"]).write_text(row["original"])
        (source / "README.md").write_text(row["contract"] + "\n")
        reference = output / "evaluator-only" / row["id"] / "reference"
        reference.mkdir(parents=True)
        (reference / row["file"]).write_text(row["reference"])
        rows.append(
            {
                "id": row["id"],
                "language": row["language"],
                "source": str(source),
                "files": 2,
                "input_regime": "known derived defect + business contract, not audit-driven or a natural CVE",
            }
        )
    save(output / "inputs.json", {"records": rows})
    save(output / "evaluator-only/dataset.json", dataset)
    packs = {}
    for language, pack in (
        ("python", audit_settings.PYTHON_QUERY_PACK),
        ("javascript", audit_settings.JAVASCRIPT_QUERY_PACK),
    ):
        packs[language] = {
            "pack": pack,
            "suite": f"codeql-suites/{language}-code-scanning.qls",
        }
    save(
        output / "config.json",
        {
            "experiment_id": output.parent.name + "-repair",
            "codeql_cli": CodeQLScanner().version(),
            "packs": packs,
            "implementation_hashes": {
                p.relative_to(ROOT).as_posix(): sha(p)
                for p in (ROOT / "system/backend/app").rglob("*")
                if p.is_file() and p.suffix in {".py", ".txt"}
            },
            "dataset_sha256": sha(output / "evaluator-only/dataset.json"),
            "source_hashes": {
                p.relative_to(output).as_posix(): sha(p)
                for p in (output / "sources").rglob("*")
                if p.is_file()
            },
            "runner_sha256": sha(Path(__file__)),
            "case_generator_sha256": sha(
                ROOT / "system/scripts/benchmarks/supplemental_repair_cases.py"
            ),
            "versions": ["1", "2"],
            "rounds": 1,
            "formal_human_reviewed_gold": False,
            "rescan": False,
            "limits": {"calls": 12, "tokens": 100000, "seconds": 240},
        },
    )


def calibrate(output):
    result = []
    for row in json.loads((output / "evaluator-only/dataset.json").read_text()):
        destination = output / "calibration" / row["id"]
        if (destination / "result.json").exists():
            result.append(json.loads((destination / "result.json").read_text()))
            continue
        pre = evaluate(destination / "original", row, output / "sources" / row["id"])
        post = evaluate(
            destination / "reference",
            row,
            output / "evaluator-only" / row["id"] / "reference",
        )
        accepted = (
            pre["normal"]["status"] == "passed"
            and pre["security"]["status"] == "failed"
            and post["joint_pass"]
        )
        item = {
            "task_id": row["id"],
            "original": pre,
            "reference": post,
            "admitted": accepted,
            "human_reviewed": False,
        }
        save(destination / "result.json", item)
        result.append(item)
        print(
            json.dumps({"task": row["id"], "calibration_admitted": accepted}),
            flush=True,
        )
    save(
        output / "calibration/summary.json",
        {
            "tasks": result,
            "admitted": sum(r["admitted"] for r in result),
            "formal_gold": False,
        },
    )


def bounded_stage(factory, audit, version, config, inputs):
    from app.persistence.stage_models import StageRun

    stage_id = factory(audit, "repair", version, inputs)
    with Session(engine) as db:
        row = db.get(StageRun, UUID(stage_id))
        row.model_config_snapshot = {
            **row.model_config_snapshot,
            "max_calls": config["limits"]["calls"],
            "max_tokens": config["limits"]["tokens"],
            "max_seconds": config["limits"]["seconds"],
        }
        db.add(row)
        db.commit()
    return stage_id


def execute(output):
    config = json.loads((output / "config.json").read_text())
    # Check original frozen input and runner before spending model budget.
    assert sha(output / "evaluator-only/dataset.json") == config["dataset_sha256"]
    assert sha(Path(__file__)) == config["runner_sha256"]
    assert (
        sha(ROOT / "system/scripts/benchmarks/supplemental_repair_cases.py")
        == config["case_generator_sha256"]
    )
    assert all(sha(output / p) == h for p, h in config["source_hashes"].items())
    assert all(sha(ROOT / p) == h for p, h in config["implementation_hashes"].items())
    admitted = {
        r["task_id"]
        for r in json.loads((output / "calibration/summary.json").read_text())["tasks"]
        if r["admitted"]
    }
    rows = {
        r["id"]: r for r in json.loads((output / "inputs.json").read_text())["records"]
    }
    # Frozen private descriptions are opened only for known-defect repair; tests stay evaluator-side.
    from scripts.benchmarks.formal_runtime import new_stage

    records = []
    for index, row in enumerate(
        json.loads((output / "evaluator-only/dataset.json").read_text())
    ):
        if row["id"] not in admitted:
            continue
        baseline = run_one(rows[row["id"]], config, 1, output=output)
        if baseline["status"] != "succeeded":
            records.append({"task_id": row["id"], "status": "infra_failure"})
            save(output / "report.json", {"records": records, "formal_gold": False})
            continue
        audit = register_audit(row["id"], output=output)
        target_file = output / "targets" / (row["id"] + ".json")
        if target_file.exists():
            candidate = UUID(json.loads(target_file.read_text())["candidate_id"])
        else:
            candidate = target(
                UUID(audit),
                {
                    "file": row["file"],
                    "line": 1,
                    "cwe": row["cwe"],
                    "description": row["contract"]
                    + " The provided implementation violates this security contract; repair the defect while retaining normal behavior.",
                },
            )
            save(
                target_file,
                {
                    "candidate_id": str(candidate),
                    "confirmation_origin": "derived_evaluator_calibration_not_human",
                },
            )
        for version in ["1", "2"] if index % 2 == 0 else ["2", "1"]:
            directory = output / "runs" / row["id"] / ("v" + version)
            generation = checkpoint_stage(
                directory / "generation.json",
                lambda version=version, audit=audit, candidate=candidate, row=row: (
                    bounded_stage(
                        new_stage,
                        audit,
                        version,
                        config,
                        {
                            "candidate_ids": [str(candidate)],
                            "allowed_paths": [row["file"]],
                            "validation_profile": "syntax",
                            "rescan": False,
                        },
                    )
                ),
                RepairService,
                build_repair_graph,
            )
            scored = directory / "scored.json"
            if scored.exists():
                records.append(json.loads(scored.read_text()))
                continue
            outcome = {"status": "not_evaluated", "joint_pass": False}
            with Session(engine) as db:
                record = db.exec(
                    select(RepairRecord).where(
                        RepairRecord.stage_id == UUID(generation["stage_id"])
                    )
                ).first()
            if record:
                artifact = ArtifactStore().directory(generation["stage_id"])
                workspace = (
                    artifact / "workspace"
                    if version == "1"
                    else artifact
                    / f"attempt-{record.validation.get('semantic_scope', {}).get('attempts')}/workspace"
                )
                if workspace.is_dir() and (workspace / row["file"]).is_file():
                    outcome = {
                        "status": "evaluated",
                        **evaluate(directory / "hidden-evaluation", row, workspace),
                    }
            item = {
                "task_id": row["id"],
                "language": row["language"],
                "version": version,
                "stage_id": generation["stage_id"],
                "status": generation["stage"]["status"],
                "seconds": generation["wall_seconds"],
                "usage": generation["stage"]["usage"],
                "model_calls": generation["stage"]["model_calls"],
                "oracle": outcome,
                "formal_gold": False,
                "end_to_end_pass": generation["stage"]["status"] == "completed"
                and outcome["joint_pass"],
            }
            save(scored, item)
            records.append(item)
            save(output / "report.json", {"records": records, "formal_gold": False})
            print(
                json.dumps(
                    {
                        "task": row["id"],
                        "version": version,
                        "status": item["status"],
                        "joint_pass": outcome["joint_pass"],
                    }
                ),
                flush=True,
            )
    assert all(sha(ROOT / p) == h for p, h in config["implementation_hashes"].items())
    save(
        output / "integrity.json",
        {"production_unchanged": True, "hidden_tests_into_model": False},
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "calibrate", "execute"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    {"prepare": prepare, "calibrate": calibrate, "execute": execute}[args.action](
        args.output.resolve()
    )


if __name__ == "__main__":
    main()
