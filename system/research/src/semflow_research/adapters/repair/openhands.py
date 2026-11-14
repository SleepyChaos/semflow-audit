"""Algorithm extracted from app.adapters.repair.openhands.

Runtime dependencies are passed explicitly; no platform ORM or configuration.
Changes to JSON require checking the corresponding semflow_contracts/wire peer.
"""

"""External pinned SDK process plus one task-owned, networkless Docker sandbox."""
import json
import os
import signal
import subprocess
import time
from pathlib import Path
from uuid import uuid4

from semflow_contracts.errors import ResearchError

from semflow_research.adapters.repair.agent_workspace import (
    export_candidate,
    writable_copy,
)
from semflow_research.adapters.repair.openhands_budget import WorkerBudget
from semflow_research.adapters.repair.openhands_receipts import publish
from semflow_research.adapters.repair.openhands_resources import (
    stage_worker,
    worker_config,
)
from semflow_research.adapters.repair.verification_runner import docker_env
from semflow_research.adapters.snapshot import snapshot_digest
from semflow_research.domain.errors import AuditError, ExecutionCancelled
from semflow_research.evidence.context_materials import save_json


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
    return max(times, default=directory.stat().st_mtime)


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
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=30,
            env=docker_env(),
            check=False,
        )
        if result.returncode:
            raise ResearchError(
                "tool_unavailable",
                "OpenHands sandbox could not start: " + result.stderr[-800:],
            )
    except (OSError, subprocess.SubprocessError, ResearchError):
        # Docker may have created the container before losing its response.
        # Cleanup is restricted to the name allocated by this invocation.
        try:
            subprocess.run(
                ["docker", "rm", "-f", name],
                capture_output=True,
                timeout=20,
                env=docker_env(),
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            pass
        raise
    return name


def generate(
    source, allowed_paths, directory, config, prompt, *, progress=None, _kernel
):
    directory.mkdir(parents=True, exist_ok=False)
    original_hash = snapshot_digest(source)
    name, process, budget = None, None, None
    status, error_code = "failed", None
    result, failure = None, None
    started = time.monotonic()
    try:
        resolved = worker_config(_kernel, config)
        python, runner = stage_worker(_kernel, directory)
        workspace = directory / "workspace"
        readable = set(_kernel.spec.inputs.patch_scope.readable_paths) | set(
            allowed_paths
        )
        writable_copy(source, workspace, allowed_paths, readable_paths=readable)
        name = start_sandbox(workspace, resolved)
        save_json(
            directory / "sandbox.json", {"name": name, "source_snapshot": original_hash}
        )
        key = _kernel.settings.OPENHANDS_API_KEY.get_secret_value()
        if (
            not key
            and config["endpoint_profile"] == _kernel.spec.model.endpoint_profile
        ):
            key = _kernel.settings.AI_API_KEY.get_secret_value()
        payload = {
            "directory": str(directory.resolve()),
            "container": name,
            "prompt": prompt,
            "model": config["model"],
            "base_url": resolved["base_url"],
            "api_key": key,
            "sdk_version": config["sdk_version"],
            "timeout": resolved["timeout"],
            "output_tokens": config["output_tokens"],
            "thinking": config["thinking_mode"],
            "max_steps": config["max_steps"],
        }
        environment = {
            **docker_env(),
            "PYTHONPATH": str(runner.parent),
            "OPENHANDS_SUPPRESS_BANNER": "1",
            "OTEL_SDK_DISABLED": "true",
        }
        budget = WorkerBudget(_kernel, directory)
        with (directory / "controller.log").open("ab") as log:
            process = subprocess.Popen(
                [str(python), str(runner)],
                stdin=subprocess.PIPE,
                stdout=log,
                stderr=subprocess.STDOUT,
                env=environment,
                start_new_session=True,
            )
            process.stdin.write(json.dumps(payload).encode())
            process.stdin.close()
            while True:
                budget.poll()
                if progress:
                    progress()
                _kernel.control.check_active(_kernel.execution_id)
                if process.poll() is not None:
                    budget.poll()
                    break
                if time.monotonic() - started >= config["timeout_seconds"]:
                    raise ResearchError(
                        "tool_failed", "OpenHands exceeded frozen timeout"
                    )
                if (
                    time.time() - latest_progress(directory)
                    >= config["stall_timeout_seconds"]
                ):
                    raise ResearchError(
                        "tool_failed",
                        "OpenHands stalled beyond frozen progress timeout",
                    )
                if (
                    _kernel.spec.policy.max_seconds
                    and time.monotonic() - started >= _kernel.spec.policy.max_seconds
                ):
                    raise ResearchError(
                        "budget_exhausted",
                        "OpenHands exceeded execution wall-time budget",
                    )
                time.sleep(0.05)
        path = directory / "runtime-result.json"
        if not path.is_file():
            raise ResearchError(
                "tool_failed", "OpenHands stopped without a complete runtime receipt"
            )
        runtime = json.loads(path.read_text())
        if runtime.get("sdk_version") != config["sdk_version"]:
            raise ResearchError(
                "identity_mismatch", "OpenHands SDK identity differs from frozen policy"
            )
        if process.returncode or runtime.get("status") != "completed":
            raise ResearchError(
                "budget_exhausted"
                if runtime.get("error_code") == "MaxIterationsReached"
                else "tool_failed",
                "OpenHands worker failed: " + str(runtime.get("error_type")),
            )
        if not budget.journal.receipts() or not any(
            row["receipt"] and row["receipt"].get("engine") == "openhands"
            for row in budget.journal.receipts()
        ):
            raise ResearchError(
                "integrity_error",
                "OpenHands completed without any journaled model call",
            )
        if budget.active:
            raise ResearchError(
                "external_outcome_unknown", "OpenHands has an unresolved model call"
            )
        if snapshot_digest(source) != original_hash:
            raise ResearchError(
                "integrity_error", "Original source changed during OpenHands execution"
            )
        for path in workspace.rglob("*"):
            if path.is_file() and not path.is_symlink():
                path.chmod(0o644)
        proposal, patch = export_candidate(
            source,
            workspace,
            allowed_paths,
            "OpenHands candidate requires independent checks and human acceptance",
        )
        save_json(directory / "candidate.json", proposal.model_dump(mode="json"))
        (directory / "repair.diff").write_text(patch)
        result = {
            "proposal": proposal.model_dump(mode="json"),
            "workspace": workspace,
            "runtime": runtime,
            "source_snapshot": original_hash,
        }
        status = "completed"
    except Exception as error:  # noqa: BLE001 — retain worker artifacts on every exit
        failure = (
            ResearchError("parse_failed", "OpenHands runtime receipt is invalid")
            if isinstance(error, (json.JSONDecodeError, KeyError))
            else ResearchError(
                "tool_unavailable", "OpenHands external resource is unavailable"
            )
            if isinstance(error, OSError)
            else ResearchError("tool_failed", "OpenHands external command failed")
            if isinstance(error, subprocess.SubprocessError)
            else error
        )
        error_code = getattr(error, "code", "tool_failed")
        status = (
            "cancelled"
            if isinstance(error, ExecutionCancelled)
            else "timed_out"
            if "timeout" in str(error).lower()
            else "failed"
        )
    finally:
        if process is not None and process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
        if budget:
            budget.abandon()
        if name:
            try:
                cleanup = subprocess.run(
                    ["docker", "rm", "-f", name],
                    capture_output=True,
                    timeout=20,
                    env=docker_env(),
                    check=False,
                )
                save_json(
                    directory / "cleanup.json", {"returncode": cleanup.returncode}
                )
            except (OSError, subprocess.TimeoutExpired) as cleanup_error:
                save_json(
                    directory / "cleanup.json",
                    {"error_type": type(cleanup_error).__name__},
                )
        workspace = directory / "workspace"
        if workspace.exists():
            workspace.chmod(0o755)
            for path in workspace.rglob("*"):
                if not path.is_symlink():
                    path.chmod(0o755 if path.is_dir() else 0o644)
        reference, members = publish(
            _kernel, directory, config, status=status, error_code=error_code
        )
        save_json(
            directory.parent / "openhands-receipt.json",
            reference.model_dump(mode="json"),
        )
    if failure:
        failure.detail, failure.artifacts = reference, members
        raise failure
    result["engine_receipt"] = reference
    return result
