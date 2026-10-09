"""Evaluator-only OCR materials, classification and native session recovery."""

import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import urlsplit

CWE = re.compile(r"\bCWE-(\d+)\b", re.IGNORECASE)
BACKGROUND = (
    "Perform a source-code security audit. For each security finding, include "
    "its explicit CWE-N identifier in the comment text when supported; otherwise "
    "state that its classification is unknown. Ground findings in source evidence."
)


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def invoke(command, environment, timeout, cwd):
    started = time.monotonic()
    process = subprocess.Popen(
        command,
        env=environment,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        os.killpg(process.pid, signal.SIGTERM)
        try:
            stdout, stderr = process.communicate(timeout=15)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            stdout, stderr = process.communicate()
    return process.returncode, stdout, stderr, time.monotonic() - started, timed_out


def model_environment(root, timeout):
    sys.path.insert(0, str(root / "backend"))
    from app.core.audit_config import audit_settings

    url, key, model = (
        audit_settings.AI_BASE_URL,
        audit_settings.AI_API_KEY.get_secret_value(),
        audit_settings.AI_MODEL,
    )
    if not url or not key or not model:
        raise ValueError("Missing configured audit model")
    parsed_url = urlsplit(url)
    if (
        parsed_url.username
        or parsed_url.password
        or parsed_url.query
        or parsed_url.fragment
    ):
        raise ValueError("Credential/query-bearing model URL is unsupported")

    def redact(value):
        return value.replace(key, "[REDACTED_TOKEN]").replace(
            url, f"{parsed_url.scheme}://{parsed_url.hostname}/[REDACTED_ENDPOINT]"
        )

    environment = {
        "OCR_LLM_URL": url,
        "OCR_LLM_TOKEN": key,
        "OCR_LLM_MODEL": model,
        "OCR_LLM_PROTOCOL": "openai",
        "OCR_LLM_TIMEOUT": str(timeout),
    }
    return environment, model, f"{parsed_url.scheme}://{parsed_url.hostname}", redact


def prepare(source):
    cases = sorted((source / "testcode").glob("Case*.py"))
    if len(cases) != 48:
        raise ValueError("Expected exactly 48 anonymous case files")
    allowed = [source / "app.py", *sorted((source / "helpers").rglob("*.py")), *cases]
    scope = Path(tempfile.mkdtemp(prefix="owasp48-ocr-", dir="/private/tmp"))
    hashes = {}
    for file in allowed:
        if not file.is_file() or not file.resolve().is_relative_to(source.resolve()):
            raise ValueError("Invalid or escaping source path")
        relative = file.relative_to(source).as_posix()
        target = scope / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file, target)
        hashes[relative] = hashlib.sha256(target.read_bytes()).hexdigest()
    return scope, [p.relative_to(source).as_posix() for p in cases], hashes


def parse_comments(comments):
    classified, unclassified = [], []
    for index, comment in enumerate(comments):
        if not isinstance(comment, dict):
            raise TypeError("Malformed comment")
        tags = sorted(
            {f"cwe-{int(n)}" for n in CWE.findall(str(comment.get("content", "")))}
        )
        row = {
            "id": f"ocr-{index}",
            "locations": [
                {
                    "file": comment.get("path"),
                    "start_line": comment.get("start_line"),
                    "end_line": comment.get("end_line"),
                }
            ],
            "cwe": tags[0] if len(tags) == 1 else "unknown",
            "tags": tags,
            "raw_comment": comment,
        }
        (classified if tags else unclassified).append(row)
    return {
        "findings": classified,
        "unclassified_comments": unclassified,
        "parser": CWE.pattern,
        "gold_used": False,
        "score_computed": False,
    }


def native_session(scope, data, cases, redact, output):
    encoded = str(scope).lstrip("/").replace("/", "-")
    directory = Path.home() / ".opencodereview/sessions" / encoded
    candidates = list(directory.glob("*.jsonl")) if directory.exists() else []
    session_id = data.get("session_id")
    path = (
        directory / f"{session_id}.jsonl"
        if session_id
        else (max(candidates, key=lambda p: p.stat().st_mtime) if candidates else None)
    )
    done, failed, requests, responses, errors, inp, out = set(), set(), 0, 0, 0, 0, 0
    malformed = 0
    if path and path.exists():
        raw = redact(path.read_text())
        (output / "session.jsonl").write_text(raw)
        for line in raw.splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                malformed += 1
                continue
            kind = row.get("type")
            file = row.get("file_path", row.get("filePath"))
            if kind in {"review_item_done", "review_item_reused"}:
                done.add(file)
            elif kind == "review_item_failed":
                failed.add(file)
            requests += kind == "llm_request"
            errors += kind == "llm_error"
            if kind == "llm_response":
                responses += 1
                usage = row.get("usage") or {}
                inp += usage.get("prompt_tokens", 0)
                out += usage.get("completion_tokens", 0)
    return {
        "native_directory": str(directory),
        "native_path": str(path) if path else None,
        "session_id": session_id,
        "completed_paths": sorted(done & set(cases)),
        "failed_paths": sorted(failed & set(cases)),
        "unknown_paths": sorted(set(cases) - done),
        "llm_requests": requests,
        "llm_responses": responses,
        "llm_errors": errors,
        "input_tokens": inp,
        "output_tokens": out,
        "malformed_records": malformed,
    }
