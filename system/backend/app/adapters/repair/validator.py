"""Trusted validation presets inside a restricted Docker container, no host shell."""

import os
import subprocess
from pathlib import Path

from app.core.audit_config import audit_settings
from app.domain.audit import AuditError

PYTHON_SYNTAX = "import pathlib; files=list(pathlib.Path('.').rglob('*.py')); assert files, 'no Python files'; [compile(p.read_text(),str(p),'exec') for p in files]; print('Python syntax checks passed:',len(files))"
JS_CHECK = "const fs=require('fs'),cp=require('child_process');function walk(p){for(const e of fs.readdirSync(p,{withFileTypes:true})){const f=p+'/'+e.name;if(e.isDirectory())walk(f);else if(/\\.(js|mjs|cjs)$/.test(f)){const r=cp.spawnSync(process.execPath,['--check',f],{stdio:'inherit'});if(r.status!==0)process.exit(1)}}}walk('.');console.log('JavaScript syntax checks passed');"


def validate_workspace(workspace: Path, language: str, profile: str) -> dict:
    if (
        profile == "python_pytest"
        and language != "python"
        or profile == "javascript_test"
        and language != "javascript"
    ):
        raise AuditError("验证配置与源码语言不匹配")
    image = (
        audit_settings.VALIDATOR_PYTHON_IMAGE
        if language == "python"
        else audit_settings.VALIDATOR_JS_IMAGE
    )
    if language == "python":
        command = (
            ["python", "-c", PYTHON_SYNTAX]
            if profile == "syntax"
            else ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider"]
        )
    else:
        command = (
            ["node", "-e", JS_CHECK] if profile == "syntax" else ["node", "--test"]
        )
    environment = {
        key: value
        for key, value in os.environ.items()
        if key in {"PATH", "HOME", "DOCKER_HOST", "DOCKER_CONTEXT"}
    }
    try:
        inspection = subprocess.run(
            ["docker", "image", "inspect", "--format", "{{.Id}}", image],
            capture_output=True,
            text=True,
            timeout=15,
            env=environment,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise AuditError("Docker 验证环境不可用") from exc
    image_id = inspection.stdout.strip()
    if inspection.returncode or not image_id.startswith("sha256:"):
        raise AuditError("验证镜像未安装；请先构建或拉取配置的镜像")
    unvalidated = [
        path.relative_to(workspace).as_posix()
        for path in workspace.rglob("*")
        if path.is_file() and path.suffix in {".ts", ".tsx", ".jsx"}
    ]
    args = [
        "docker",
        "run",
        "--rm",
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
        "--env=HOME=/tmp",
        "--workdir=/workspace",
        "--mount",
        f"type=bind,src={workspace.resolve()},dst=/workspace,readonly",
        image_id,
        *command,
    ]
    container_name = "audit-check-" + workspace.parent.name
    args[2:2] = ["--name", container_name]
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=audit_settings.VALIDATOR_TIMEOUT,
            env=environment,
        )
    except subprocess.TimeoutExpired:
        subprocess.run(
            ["docker", "rm", "-f", container_name], capture_output=True, timeout=15
        )
        return {
            "status": "failed",
            "reason": "隔离验证超时",
            "profile": profile,
            "image": image,
        }
    except OSError as exc:
        raise AuditError("Docker 验证环境不可用") from exc
    output = (result.stdout + result.stderr)[-20000:]
    status = "passed" if result.returncode == 0 else "failed"
    if language == "javascript" and (
        profile == "syntax"
        and unvalidated
        or profile == "javascript_test"
        and "# tests 0" in output
    ):
        status = "needs_review"
    return {
        "status": status,
        "exit_code": result.returncode,
        "output": output,
        "profile": profile,
        "image": image,
        "image_id": image_id,
        "network": "none",
        "read_only": True,
        "unvalidated_files": unvalidated if profile == "syntax" else [],
        "semantic_limit": "syntax only; TypeScript/JSX require project-specific compilation/tests"
        if profile == "syntax"
        else "project tests executed; no dependencies installed automatically",
    }
