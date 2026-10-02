import os
import signal
import subprocess
from pathlib import Path

from app.domain.audit import AuditError

# Source extraction processes receive no service credentials.
ENV_KEYS = {"PATH", "HOME", "TMPDIR", "LANG", "LC_ALL", "JAVA_HOME", "SYSTEMROOT"}


def run_command(
    args: list[str], log: Path, timeout: int, runtime_path: Path | None = None
) -> None:
    environment = {key: value for key, value in os.environ.items() if key in ENV_KEYS}
    if runtime_path is not None:
        environment["PATH"] = (
            str(runtime_path) + os.pathsep + environment.get("PATH", "")
        )
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a") as stream:
        stream.write("\n$ " + " ".join(args) + "\n")
        stream.flush()
        try:
            process = subprocess.Popen(
                args,
                stdout=stream,
                stderr=subprocess.STDOUT,
                env=environment,
                start_new_session=True,
            )
        except OSError as exc:
            raise AuditError("无法启动 CodeQL，请检查执行环境") from exc
        try:
            code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            raise AuditError("CodeQL 执行超时；请查看执行日志") from exc
    if code:
        raise AuditError(f"CodeQL 命令失败（退出码 {code}）；请查看执行日志")
