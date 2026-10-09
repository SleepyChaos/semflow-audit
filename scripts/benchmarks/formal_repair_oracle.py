"""Run evaluator-only derived module tests inside the existing restricted image."""

import json
import shutil
import subprocess

from scripts.benchmarks.formal_freeze import OUTPUT, ROOT, save

PREPARATION = ROOT / "artifacts/research/formal-preparation/repair-calibration"
CASE = "pair-a0a4ebc7815b308f"


def evaluate(directory, patched=None):
    directory.mkdir(parents=True, exist_ok=True)
    source = directory / "sources"
    if not source.exists():
        shutil.copytree(PREPARATION / "sources", source)
    if patched is not None:
        shutil.copyfile(patched / "lib/util.js", source / CASE / "pre/lib/util.js")
    shutil.copyfile(PREPARATION / "unit_oracles.cjs", directory / "oracle.cjs")
    image = subprocess.check_output(
        ["docker", "image", "inspect", "--format", "{{.Id}}", "node:22-bookworm-slim"],
        text=True,
    ).strip()
    command = (
        "process.argv=['node','/eval/oracle.cjs','/eval/sources','/tmp/result.json'];"
        "require('/eval/oracle.cjs');"
        "console.log('FULL_RESULT='+require('fs').readFileSync('/tmp/result.json','utf8'));"
    )
    result = subprocess.run(
        [
            "docker",
            "run",
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
            "--mount",
            f"type=bind,src={directory.resolve()},dst=/eval,readonly",
            image,
            "node",
            "-e",
            command,
        ],
        capture_output=True,
        text=True,
        timeout=45,
        check=False,
    )
    (directory / "stdout.txt").write_text(result.stdout)
    (directory / "stderr.txt").write_text(result.stderr)
    if result.returncode or "FULL_RESULT=" not in result.stdout:
        receipt = {"status": "infra_failure", "exit_code": result.returncode}
    else:
        full = json.loads(result.stdout.split("FULL_RESULT=", 1)[1])
        row = next(r for r in full["cases"] if r["case_id"] == CASE)
        target = row["versions"]["pre"]
        receipt = {
            "status": "evaluated",
            "runtime": full["runtime"],
            "image": image,
            "oracle_origin": "derived-agent-authored-not-human-reviewed",
            "scope": "sanitizer lexical boundary; no downstream shell/service exploit",
            "functional": target.get("functional"),
            "security": target.get("security"),
            "official_calibration": row["calibration_status"]
            if patched is None
            else "not_applicable_to_candidate",
            "joint_pass": all(
                t["status"] == "pass" for t in target.get("functional", [])
            )
            and all(t["status"] == "pass" for t in target.get("security", []))
            and bool(target.get("functional"))
            and bool(target.get("security")),
        }
        save(directory / "full-result.json", full)
    save(directory / "oracle-result.json", receipt)
    return receipt


if __name__ == "__main__":
    print(json.dumps(evaluate(OUTPUT / "repair/original-container-calibration")))
