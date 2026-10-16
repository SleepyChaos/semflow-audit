"""Run a checkpointed command DAG in one process; no agent or scheduler required."""

import argparse
import fcntl
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


def stamp():
    return datetime.now(timezone.utc).isoformat()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


@contextmanager
def exclusive(path, *, blocking=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
        except BlockingIOError as error:
            raise RuntimeError("Another pipeline owns this output") from error
        handle.seek(0)
        handle.truncate()
        handle.write(str(os.getpid()))
        handle.flush()
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def validate(plan):
    seen = set()
    for step in plan["steps"]:
        if step["id"] in seen or not step["id"].replace("-", "").isalnum():
            raise ValueError("Invalid or repeated step identity")
        if not set(step.get("depends_on", [])) <= seen:
            raise ValueError("Dependencies must precede their consumer")
        if not step.get("argv") or not all(isinstance(v, str) for v in step["argv"]):
            raise ValueError("Commands must be argument arrays, not shell programs")
        if step.get("timeout_seconds", 86400) <= 0:
            raise ValueError("Step timeout must be positive")
        seen.add(step["id"])


def run_step(step, cwd, output, environment):
    identifier = step["id"]
    log = output / "logs" / f"{identifier}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    argv = [sys.executable if x == "{python}" else x for x in step["argv"]]
    with log.open("ab") as stream:
        process = subprocess.Popen(
            argv,
            cwd=cwd,
            env=environment,
            stdout=stream,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        receipt = {
            "step": identifier,
            "status": "running",
            "started_at": stamp(),
            "pid": process.pid,
            "controller_pid": os.getpid(),
            "log": str(log),
        }
        try:
            while process.poll() is None:
                receipt.update(
                    heartbeat_at=stamp(),
                    elapsed_seconds=round(time.monotonic() - started, 1),
                    log_bytes=log.stat().st_size,
                )
                save(output / "status.json", receipt)
                if time.monotonic() - started > step.get("timeout_seconds", 86400):
                    raise TimeoutError("Owned step exceeded wall-clock safety limit")
                time.sleep(2)
        except BaseException:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
            receipt.update(status="interrupted", finished_at=stamp())
            save(output / "status.json", receipt)
            raise
    receipt.update(
        status="completed" if process.returncode == 0 else "blocked",
        exit_code=process.returncode,
        finished_at=stamp(),
        elapsed_seconds=round(time.monotonic() - started, 1),
    )
    save(output / "status.json", receipt)
    if process.returncode:
        raise RuntimeError(f"Step {identifier} failed; inspect {log}")
    return receipt


def execute(plan_path, output):
    plan = json.loads(plan_path.read_text())
    validate(plan)
    identity = hashlib.sha256(plan_path.read_bytes()).hexdigest()
    cwd = Path(plan["cwd"]).resolve()
    environment = {**os.environ, **plan.get("env", {})}
    with exclusive(Path(plan.get("lock_path", output / "pipeline.lock"))):
        output.mkdir(parents=True, exist_ok=True)
        frozen = output / "plan.json"
        if frozen.exists() and frozen.read_bytes() != plan_path.read_bytes():
            raise RuntimeError("Execution plan changed; use a new run directory")
        if not frozen.exists():
            frozen.write_bytes(plan_path.read_bytes())
        for step in plan["steps"]:
            checkpoint = output / "steps" / f"{step['id']}.json"
            if checkpoint.exists():
                previous = json.loads(checkpoint.read_text())
                if (
                    previous.get("plan_hash") != identity
                    or previous["status"] != "completed"
                ):
                    raise RuntimeError("Invalid completed checkpoint")
                continue
            try:
                receipt = run_step(step, cwd, output, environment)
            except (RuntimeError, OSError, TimeoutError) as error:
                save(
                    output / "failure.json",
                    {
                        "step": step["id"],
                        "status": "blocked",
                        "error": str(error),
                        "observed_at": stamp(),
                        "automatic_paid_retry": False,
                    },
                )
                raise
            save(checkpoint, {**receipt, "plan_hash": identity})
        save(output / "status.json", {"status": "completed", "finished_at": stamp()})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        execute(args.plan.resolve(), args.output.resolve())
    except (RuntimeError, OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
