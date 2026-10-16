"""Full Vul4Py dual-oracle calibration with isolated setup and networkless tests."""

import argparse
import json
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4
from xml.etree import ElementTree

from scripts.benchmarks.vul4py_prepare import save

ROOT = Path(__file__).resolve().parents[3]


def junit(path):
    if not path.exists():
        return {"status": "missing", "tests": 0, "failures": 0, "errors": 0}
    try:
        root = ElementTree.parse(path).getroot()
        rows = list(root.iter("testcase"))
        return {
            "status": "parsed",
            "tests": len(rows),
            "failures": sum(r.find("failure") is not None for r in rows),
            "errors": sum(r.find("error") is not None for r in rows),
            "skipped": sum(r.find("skipped") is not None for r in rows),
        }
    except (OSError, ElementTree.ParseError):
        return {"status": "invalid", "tests": 0, "failures": 0, "errors": 0}


def test_pass(rc, report):
    return (
        rc == 0
        and report["status"] == "parsed"
        and report["tests"] > report.get("skipped", 0)
        and report["failures"] == report["errors"] == 0
    )


def dual_verdict(results, reports):
    functional = all(
        test_pass(results[t]["functional_rc"], reports[t]["functional"])
        for t in ("vulnerable", "fixed")
    )
    negative = (
        results["vulnerable"]["exploit_rc"] == 1
        and reports["vulnerable"]["exploit"]["failures"] > 0
        and reports["vulnerable"]["exploit"]["errors"] == 0
    )
    positive = test_pass(results["fixed"]["exploit_rc"], reports["fixed"]["exploit"])
    return {
        "functional_calibrated": functional,
        "exploit_calibrated": negative and positive,
        "accepted": functional and negative and positive,
        "meaning": "actual nonempty functional pass both versions; genuine security assertion failure before and pass after; rc999 never passes",
    }


def container(case, output, mode, image, targets=None, dependency_profile=None):
    started = time.perf_counter()
    name = "vul4py-oracle-" + uuid4().hex
    tools = output / "evaluator-tools"
    tools.mkdir(exist_ok=True)
    command = [
        "docker",
        "run",
        "--name",
        name,
        "--rm",
        "--pull=never",
        "--network=" + ("bridge" if mode == "setup" else "none"),
        "--read-only",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        "--pids-limit=256",
        "--memory=2g",
        "--cpus=2",
        "--tmpfs=/tmp:rw,nosuid,size=512m",
        "--env=HOME=/tmp",
        "--env=PYTHONDONTWRITEBYTECODE=1",
        "--env=PIP_DISABLE_PIP_VERSION_CHECK=1",
        "--env=PYTHONPATH=/runner",
        "--mount",
        f"type=bind,src={case},dst=/cases/{case.name}",
        "--mount",
        f"type=bind,src={tools},dst=/tools",
        "--mount",
        f"type=bind,src={output / 'upstream'},dst=/official,readonly",
        "--mount",
        f"type=bind,src={ROOT / 'system/scripts'},dst=/runner/scripts,readonly",
        "--entrypoint",
        "/usr/local/bin/python3",
        image,
        "-m",
        "scripts.benchmarks.vul4py_container",
        "--case",
        "/cases/" + case.name,
        "--mode",
        mode,
    ]
    if targets:
        command += ["--targets", *targets]
    if dependency_profile:
        command += ["--test-dependencies", dependency_profile]
    if dependency_profile == "project-compatible":
        command[command.index("--entrypoint") : command.index("--entrypoint")] = [
            "--mount",
            f"type=bind,src={output / 'environment-profile.json'},dst=/environment-profile.json,readonly",
        ]
    limit = 1800 if mode == "setup" else 1300
    try:
        result = subprocess.run(
            command, capture_output=True, timeout=limit, check=False
        )
        (case / f"{mode}.stdout.log").write_bytes(result.stdout)
        (case / f"{mode}.stderr.log").write_bytes(result.stderr)
        return {
            "status": "succeeded" if result.returncode == 0 else "failed",
            "exit_code": result.returncode,
            "seconds": time.perf_counter() - started,
            "network": "bridge" if mode == "setup" else "none",
        }
    except subprocess.TimeoutExpired as error:
        subprocess.run(
            ["docker", "rm", "-f", name], capture_output=True, timeout=20, check=False
        )
        (case / f"{mode}.stdout.log").write_bytes(error.stdout or b"")
        (case / f"{mode}.stderr.log").write_bytes(error.stderr or b"")
        return {"status": "timeout", "seconds": time.perf_counter() - started}


def calibrate(identity, output, image, dependency_profile=None):
    path = output / "calibration" / identity / "result.json"
    if path.exists():
        return json.loads(path.read_text())
    receipt = json.loads((output / "acquisition" / f"{identity}.json").read_text())
    verdict = {
        "vuln_id": identity,
        "accepted": False,
        "status": "not_evaluated",
        "image_id": image,
    }
    if receipt["status"] != "prepared":
        verdict.update(reason="source_preparation_failed")
    else:
        source = output / "workspaces" / identity
        meta = json.loads((source / "meta.json").read_text())
        if not meta["new_test_files"] or not meta["baseline_test_files"]:
            verdict.update(reason="missing_security_or_functional_test_files")
        else:
            case = output / "evaluator" / identity
            case.mkdir(parents=True, exist_ok=True)
            if not (case / "meta.json").exists():
                for target in ("vulnerable", "fixed"):
                    shutil.copytree(source / target, case / target, symlinks=True)
                shutil.copyfile(source / "meta.json", case / "meta.json")
            setup = container(
                case, output, "setup", image, dependency_profile=dependency_profile
            )
            if dependency_profile:
                verdict["dependency_profile"] = dependency_profile
            verdict["setup"] = setup
            if setup["status"] != "succeeded":
                verdict.update(
                    status="environment_failed", reason="dependency_setup_failed"
                )
            else:
                checks = container(
                    case, output, "tests", image, dependency_profile=dependency_profile
                )
                verdict["execution"] = checks
                if checks["status"] != "succeeded":
                    verdict.update(
                        status="environment_failed", reason="oracle_execution_failed"
                    )
                else:
                    results = json.loads((case / "tests-result.json").read_text())
                    reports = {
                        t: {
                            k: junit(case / "logs" / f"{k}_{t}.junit.xml")
                            for k in ("functional", "exploit")
                        }
                        for t in ("vulnerable", "fixed")
                    }
                    verdict.update(dual_verdict(results, reports))
                    verdict.update(
                        status="accepted"
                        if verdict["accepted"]
                        else "oracle_not_calibrated",
                        results=results,
                        junit=reports,
                    )
    save(path, verdict)
    print(identity, verdict["status"], flush=True)
    return verdict


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--projects", nargs="+")
    args = parser.parse_args()
    output = args.output.resolve()
    image = subprocess.check_output(
        [
            "docker",
            "image",
            "inspect",
            "--format",
            "{{.Id}}",
            "codeql-platform:with-gcc",
        ],
        text=True,
    ).strip()
    manifest = json.loads((output / "manifest.json").read_text())
    ids = [r["vuln_id"] for r in manifest["cases"]]
    if args.projects:
        if not set(args.projects) <= set(ids):
            raise RuntimeError("Unknown case ID")
        ids = args.projects
    save(
        output / "oracle-config.json",
        {
            "image_id": image,
            "architecture": "linux/amd64",
            "jobs": args.jobs,
            "python_match": "exact minor version; otherwise official micromamba",
            "functional_missing_not_pass": True,
            "model_calls": 0,
        },
    )
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        rows = list(pool.map(lambda identity: calibrate(identity, output, image), ids))
    save(
        output / "calibration-summary.json",
        {
            "cases": rows,
            "attempted": len(rows),
            "accepted": sum(r["accepted"] for r in rows),
            "total_frozen": 100,
            "model_repair_not_run": True,
        },
    )


if __name__ == "__main__":
    main()
