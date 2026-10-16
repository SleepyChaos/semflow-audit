"""Run one frozen external suite in a constrained container; parse real reports."""

import os
import re
import subprocess
from pathlib import Path
from uuid import uuid4
from xml.etree import ElementTree

from app.adapters.repair.bounded_process import execute_bounded
from app.core.audit_config import audit_settings
from app.domain.audit import AuditError

NODE_REPORTER = (
    Path(__file__)
    .with_name("node_verification_reporter.cjs")
    .read_text(encoding="utf-8")
)


def is_assertion_failure(failure, language):
    # Inspect the actual exception header, never arbitrary traceback substrings.
    message = failure.get("message", "").lstrip()
    if language == "python":
        return bool(
            re.match(
                r"^(?:AssertionError(?:\b|:)|assert\s|Failed:\s+DID NOT RAISE\b)",
                message,
            )
        )
    return failure.get("type") == "AssertionError"


def parse_results(xml, exit_code, suite):
    if (
        len(xml.encode()) > 2_000_000
        or "<!DOCTYPE" in xml.upper()
        or "<!ENTITY" in xml.upper()
    ):
        raise AuditError("测试报告包含不允许的声明或超过大小限制")
    try:
        tree = ElementTree.fromstring(xml)
    except ElementTree.ParseError as exc:
        raise AuditError("测试报告无效，不能判断修复") from exc
    cases, duplicate = {}, False
    for node in tree.iter("testcase"):
        name = node.get("name", "")
        duplicate |= name in cases
        error, failure, skipped = (
            node.find("error"),
            node.find("failure"),
            node.find("skipped"),
        )
        detail = error if error is not None else failure
        output = (
            ""
            if detail is None
            else " ".join([*detail.attrib.values(), detail.text or ""])
        )
        status = (
            "error"
            if error is not None
            else "skipped"
            if skipped is not None
            else "passed"
        )
        if failure is not None:
            status = (
                "assertion_failed"
                if is_assertion_failure(failure, suite.language)
                else "error"
            )
        message = "" if detail is None else detail.get("message", "").strip()
        exception = re.match(r"^([A-Za-z_][A-Za-z_0-9.]*)(?=:|$)", message)
        locations = re.findall(
            r"(?m)^([^\s].*?\.py):([0-9]+): ([A-Za-z_][\w.]*)\s*$",
            "" if detail is None else detail.text or "",
        )
        location = next(
            (
                row
                for row in reversed(locations)
                if exception and row[2] == exception.group(1)
            ),
            None,
        )
        cases[name] = {
            "exception_file": location[0] if location else None,
            "exception_line": int(location[1]) if location else None,
            "status": status,
            "output": output[-4000:],
            "exception_type": exception.group(1) if exception else None,
            "exception_message": message[:500],
        }
    expected = {case.name for case in suite.cases}
    complete = not duplicate and set(cases) == expected and exit_code in {0, 1}
    if exit_code == 0 and any(row["status"] != "passed" for row in cases.values()):
        complete = False
    if exit_code == 1 and not any(row["status"] != "passed" for row in cases.values()):
        complete = False
    return {
        "status": "completed" if complete else "inconclusive",
        "exit_code": exit_code,
        "cases": cases,
        "unexpected_cases": sorted(set(cases) - expected),
        "missing_cases": sorted(expected - set(cases)),
    }


def docker_env():
    return {
        key: value
        for key, value in os.environ.items()
        if key in {"PATH", "HOME", "DOCKER_HOST", "DOCKER_CONTEXT"}
    }


def resolve_image(image):
    try:
        result = subprocess.run(
            ["docker", "image", "inspect", "--format", "{{.Id}}", image],
            capture_output=True,
            text=True,
            timeout=15,
            env=docker_env(),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise AuditError("Docker 不可用，前后对比未执行") from exc
    image_id = result.stdout.strip()
    if result.returncode or not image_id.startswith("sha256:"):
        raise AuditError("项目验证镜像未安装，请先构建包含项目依赖的镜像")
    return image_id


def run_suite(
    workspace: Path, suite_directory: Path, suite, image_id, output_directory: Path
):
    output_directory.mkdir(parents=True, exist_ok=False)
    name = "audit-compare-" + uuid4().hex
    files = [f"/suite/{name}" for name in suite.files]
    if suite.language == "python":
        executable, command = (
            "python",
            [
                "-m",
                "pytest",
                "-q",
                "-p",
                "no:cacheprovider",
                "-c",
                "/suite/pytest.ini",
                "--confcutdir=/suite",
                "--import-mode=importlib",
                "--junitxml=/tmp/verification.xml",
                *files,
            ],
        )
    else:
        executable, command = (
            "node",
            [
                "--test",
                "--test-reporter=/suite/verification-reporter.cjs",
                "--test-reporter-destination=/tmp/verification.xml",
                *files,
            ],
        )
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
        "--pids-limit=128",
        "--memory=512m",
        "--cpus=1",
        "--user=65534:65534",
        "--tmpfs=/tmp:rw,noexec,nosuid,size=128m",
        "--env=PYTHONDONTWRITEBYTECODE=1",
        "--env=PYTEST_DISABLE_PLUGIN_AUTOLOAD=1",
        "--env=PYTHONPATH=/workspace",
        "--env=HOME=/tmp",
        "--env=NODE_OPTIONS=",
        "--workdir=/workspace",
        "--mount",
        f"type=bind,src={workspace.resolve()},dst=/workspace,readonly",
        "--mount",
        f"type=bind,src={suite_directory.resolve()},dst=/suite,readonly",
        "--entrypoint",
        executable,
        image_id,
        *(
            ["-I", "-S", "-c", "import time; time.sleep(600)"]
            if executable == "python"
            else ["-e", "setTimeout(() => {}, 600000)"]
        ),
    ]
    try:
        started = subprocess.run(
            args, capture_output=True, text=True, timeout=30, env=docker_env()
        )
        if started.returncode:
            return {
                "status": "blocked",
                "cases": {},
                "output": started.stderr[-4000:],
                "reason": "验证容器未能启动，请检查 Docker 和镜像",
            }
        # Keep tmpfs mounted until its report has been copied. Stopping PID 1
        # before reading it discards /tmp and loses otherwise successful tests.
        result = execute_bounded(
            ["docker", "exec", name, executable, *command],
            audit_settings.VALIDATOR_TIMEOUT,
            docker_env(),
        )
        output = result["output"]
        (output_directory / "output.txt").write_text(output, encoding="utf-8")
        if result["reason"]:
            return {
                "status": "blocked",
                "cases": {},
                "output": output,
                "reason": result["reason"],
            }
        reader = (
            [
                "-I",
                "-S",
                "-c",
                "import sys;sys.stdout.buffer.write(open('/tmp/verification.xml','rb').read(2000001))",
            ]
            if executable == "python"
            else [
                "-e",
                "const fs=require('fs');const b=Buffer.alloc(2000001);const f=fs.openSync('/tmp/verification.xml','r');const n=fs.readSync(f,b,0,b.length,0);process.stdout.write(b.subarray(0,n));",
            ]
        )
        copied = execute_bounded(
            ["docker", "exec", name, executable, *reader],
            15,
            docker_env(),
            output_limit=2_000_000,
            tail_limit=2_000_000,
        )
        if copied["exit_code"] or copied["reason"]:
            return {
                "status": "blocked",
                "cases": {},
                "output": output,
                "reason": copied["reason"]
                or "未产生逐项测试报告，请检查镜像依赖和启动错误",
                "report_error": copied["output"][-2000:],
            }
        (output_directory / "results.xml").write_text(
            copied["output"], encoding="utf-8"
        )
        parsed = parse_results(
            copied["output"],
            result["exit_code"],
            suite,
        )
        return {**parsed, "output": output, "image_id": image_id}
    except subprocess.TimeoutExpired:
        return {"status": "blocked", "cases": {}, "reason": "测试超时，不能判断修复"}
    except OSError as exc:
        raise AuditError("Docker 对比运行失败") from exc
    finally:
        subprocess.run(
            ["docker", "rm", "-f", name],
            capture_output=True,
            timeout=15,
            env=docker_env(),
        )
