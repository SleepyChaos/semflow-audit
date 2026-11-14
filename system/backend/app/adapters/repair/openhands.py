"""External pinned SDK process plus one task-owned, networkless Docker sandbox."""

import json
import subprocess
import time
from pathlib import Path
from uuid import uuid4

from app.adapters.repair.agent_workspace import export_candidate, writable_copy
from app.adapters.repair.verification_runner import docker_env
from app.adapters.snapshot import snapshot_digest
from app.core.audit_config import ROOT, audit_settings
from app.domain.audit import AuditError
from app.services.context_materials import save_json


def latest_progress(directory):
    """SDK atomically rotates private state; only stable event receipts count."""
    paths = [
        *directory.glob("*.json"),
        directory / "events.jsonl",
        directory / "controller.log",
    ]
    times = []
    for path in paths:
        try:
            times.append(path.stat().st_mtime)
        except FileNotFoundError:
            continue
    return max(times, default=time.time())


def start_sandbox(workspace, config):
    name = "semflow-openhands-" + uuid4().hex
    args = [
        "docker",
        "run",
        "--detach",
        "--name",
        name,
        "--pull=never",
        "--network=none",
        "--read-only",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        "--pids-limit=256",
        "--memory=2g",
        "--cpus=2",
        "--user=65534:65534",
        "--tmpfs=/tmp:rw,exec,nosuid,size=512m",
        "--env=HOME=/tmp",
        "--env=PYTHONDONTWRITEBYTECODE=1",
        "--env=PYTEST_DISABLE_PLUGIN_AUTOLOAD=1",
        "--env=PYTHONPATH=/workspace:/workspace/src",
        "--workdir=/workspace",
        "--mount",
        f"type=bind,src={workspace.resolve()},dst=/workspace",
    ]
    if config.get("dependency_environment"):
        if config.get("dependency_tools"):
            tools = Path(config["dependency_tools"]).resolve()
            if not tools.is_dir():
                raise AuditError(
                    "Project interpreter tools missing",
                    code="dependency_environment_unavailable",
                )
            args += ["--mount", f"type=bind,src={tools},dst=/tools,readonly"]
        env = Path(config["dependency_environment"]).resolve()
        if not (env / "pyvenv.cfg").is_file():
            raise AuditError(
                "Project dependency environment missing",
                code="dependency_environment_unavailable",
            )
        args += [
            "--mount",
            f"type=bind,src={env},dst=/opt/deps,readonly",
            "--env=PATH=/opt/deps/bin:/usr/local/bin:/usr/bin:/bin",
        ]
        versions = list((env / "lib").glob("python*/site-packages"))
        if len(versions) != 1:
            raise AuditError(
                "Project Python dependency path is ambiguous",
                code="dependency_environment_unavailable",
            )
        args += [
            "--env=PYTHONPATH=/workspace:/workspace/src:/opt/deps/"
            + str(versions[0].relative_to(env))
        ]
    if config.get("development_suite"):
        suite = Path(config["development_suite"]).resolve()
        args += ["--mount", f"type=bind,src={suite},dst=/development,readonly"]
    args += ["--entrypoint", "/bin/sleep", config["image_id"], "infinity"]
    result = subprocess.run(
        args, capture_output=True, text=True, timeout=30, env=docker_env()
    )
    if result.returncode:
        raise AuditError("OpenHands sandbox could not start: " + result.stderr[-800:])
    return name


def generate(source, allowed_paths, directory, config, prompt, *, progress=None):
    directory.mkdir(parents=True, exist_ok=False)
    original_hash = snapshot_digest(source)
    workspace = directory / "workspace"
    writable_copy(source, workspace, allowed_paths)
    runtime = ROOT / "system/agents/openhands"
    python = Path(audit_settings.OPENHANDS_PYTHON or runtime / ".venv/bin/python")
    runner = runtime / "runner.py"
    if not python.is_file():
        raise AuditError("Pinned OpenHands runtime is not installed")
    name = start_sandbox(workspace, config)
    save_json(
        directory / "sandbox.json", {"name": name, "source_snapshot": original_hash}
    )
    payload = {
        "directory": str(directory.resolve()),
        "container": name,
        "prompt": prompt,
        "model": config["model"],
        "base_url": config["base_url"],
        "api_key": audit_settings.AI_API_KEY.get_secret_value(),
        "timeout": config.get("timeout", 90),
        "output_tokens": config.get("output_tokens", 6000),
        "thinking": config.get("thinking_mode"),
        "max_steps": config.get("max_steps", 100),
    }
    environment = {
        **docker_env(),
        "PYTHONPATH": str(ROOT / "system/backend"),
        "OPENHANDS_SUPPRESS_BANNER": "1",
        "OTEL_SDK_DISABLED": "true",
    }
    process = None
    started = time.monotonic()
    try:
        with (directory / "controller.log").open("ab") as log:
            process = subprocess.Popen(
                [str(python), str(runner)],
                stdin=subprocess.PIPE,
                stdout=log,
                stderr=subprocess.STDOUT,
                env=environment,
            )
            process.stdin.write(json.dumps(payload).encode())
            process.stdin.close()
            while process.poll() is None:
                if progress:
                    progress()
                last = latest_progress(directory)
                if time.time() - last > 240 or time.monotonic() - started > 1800:
                    raise AuditError(
                        "OpenHands progress stalled; artifacts retained",
                        code="agent_stalled",
                    )
                time.sleep(2)
        result = directory / "runtime-result.json"
        if not result.exists():
            raise AuditError("OpenHands runtime stopped without a complete receipt")
        result = json.loads(result.read_text())
        if process.returncode or result["status"] != "completed":
            if result.get("error_code") == "MaxIterationsReached":
                raise AuditError(
                    "OpenHands exhausted its iteration limit; candidate was not accepted",
                    code="candidate_iteration_limit",
                )
            raise AuditError(
                "OpenHands failed: " + str(result.get("error_type")),
                code="agent_failed",
            )
        if snapshot_digest(source) != original_hash:
            raise AuditError(
                "Original snapshot changed during agent execution",
                code="integrity_error",
            )
        proposal, patch = export_candidate(
            source,
            workspace,
            allowed_paths,
            "OpenHands 修复候选已导出；平台独立检查和人工验收仍为必要步骤",
        )
        save_json(directory / "candidate.json", proposal.model_dump(mode="json"))
        (directory / "repair.diff").write_text(patch)
        return {
            "proposal": proposal.model_dump(mode="json"),
            "workspace": workspace,
            "runtime": result,
            "source_snapshot": original_hash,
        }
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        subprocess.run(
            ["docker", "rm", "-f", name],
            capture_output=True,
            timeout=20,
            env=docker_env(),
        )
