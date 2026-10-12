"""Bound untrusted container output while it is produced, not after capture."""

import subprocess
from threading import Event, Thread

OUTPUT_LIMIT = 2_000_000
TAIL_LIMIT = 20_000


def execute_bounded(
    args, timeout, env, *, output_limit=OUTPUT_LIMIT, tail_limit=TAIL_LIMIT
):
    process = subprocess.Popen(
        args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env
    )
    tail = bytearray()
    exceeded = Event()
    read_error = Event()

    def read_output():
        count = 0
        try:
            while block := process.stdout.read(4096):
                count += len(block)
                tail.extend(block)
                if len(tail) > tail_limit:
                    del tail[:-tail_limit]
                if count > output_limit:
                    exceeded.set()
                    process.kill()
                    break
        except OSError:
            read_error.set()

    reader = Thread(target=read_output, daemon=True)
    reader.start()
    reason = None
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        reason = "测试超时，不能判断修复"
        process.kill()
        process.wait(timeout=5)
    reader.join(timeout=2)
    if exceeded.is_set():
        reason = "测试输出超过限制，运行已终止；不能判断修复"
    elif read_error.is_set() or reader.is_alive():
        reason = "测试输出读取未完成，不能判断修复"
    if not reader.is_alive():
        process.stdout.close()
    return {
        "exit_code": process.returncode,
        "output": bytes(tail).decode("utf-8", errors="replace"),
        "reason": reason,
    }
