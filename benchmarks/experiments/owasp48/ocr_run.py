"""Real fixed-source OCR runner; defaults to zero-model preview, never reads gold."""

import argparse
import hashlib
import json
import os
from pathlib import Path

from ocr_support import (
    BACKGROUND,
    invoke,
    model_environment,
    native_session,
    parse_comments,
    prepare,
    save,
)

ROOT = Path(__file__).resolve().parents[3]
BINARY = ROOT / "artifacts/competitors/ocr"
BASE = ROOT / "artifacts/research/owasp48/20261007-evolution"
TOKEN_CAP = 1800000
WALL_CAP = 1800
MODEL_TIMEOUT = 90


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("--sample", default="acceptance-01")
    cli.add_argument("--output", type=Path, required=True)
    cli.add_argument(
        "--execute", action="store_true", help="Enable real paid-model scan"
    )
    args = cli.parse_args()
    if "/" in args.sample or args.sample in {".", ".."}:
        raise ValueError("Invalid sample identifier")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if (output / "receipt.json").exists():
        raise ValueError("Existing receipt must not be overwritten; use a fresh output")
    for name in ("config.json", "rule.json"):
        if (Path.home() / ".opencodereview" / name).exists():
            raise ValueError("Uncontrolled global OCR configuration/rules present")
    scope, cases, hashes = prepare(BASE / "samples" / args.sample / "source")
    environment = os.environ.copy()
    for name in ("GIT_DIR", "GIT_WORK_TREE"):
        environment.pop(name, None)
    environment.update(OCR_RAW_LOGGING="0", OCR_ENABLE_TELEMETRY="0")
    command = [
        str(BINARY),
        "scan",
        "--repo",
        str(scope),
        "--path",
        ",".join(cases),
        "--format",
        "json",
        "--output",
        "-",
    ]
    receipt = {
        "schema_version": 1,
        "status": "prepared",
        "sample": args.sample,
        "source_scope": str(scope),
        "source_sha256": hashes,
        "case_paths": cases,
        "ocr_commit": "a758d9cbfb689937c7857ad64b2dd66adb58c0c2",
        "binary_sha256": hashlib.sha256(BINARY.read_bytes()).hexdigest(),
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "support_sha256": hashlib.sha256(
            (Path(__file__).parent / "ocr_support.py").read_bytes()
        ).hexdigest(),
        "scoring_contract": {
            "explicit_comment_cwe_regex": r"\bCWE-(\d+)\b",
            "gold_used": False,
            "classification_inference": False,
        },
        "settings": {
            "concurrency": 3,
            "token_cap": TOKEN_CAP,
            "wall_seconds": WALL_CAP,
            "model_timeout_seconds": MODEL_TIMEOUT,
            "default_plan": True,
            "default_dedup": True,
            "default_summary": True,
        },
        "limitations": [
            "Token cap is pre-dispatch/pre-round and may overshoot.",
            "OCR default 60 tool rounds is not platform call-cap alignment.",
            "summary.files_reviewed is selected count, not completed count.",
            "No-CWE comments require separate blind diagnostic adjudication.",
        ],
        "model_calls": 0,
        "preview_command": command + ["--preview"],
    }
    save(output / "receipt.json", receipt)
    rc, stdout, stderr, wall, expired = invoke(
        command + ["--preview"], environment, 60, ROOT
    )
    (output / "preview.stdout.txt").write_text(stdout)
    (output / "preview.stderr.txt").write_text(stderr)
    try:
        preview = json.loads(stdout)
        if not isinstance(preview, dict):
            raise TypeError("Malformed preview")
    except (ValueError, TypeError):
        receipt.update(status="failed_preview_output", preview_rc=rc)
        save(output / "receipt.json", receipt)
        return 1
    save(output / "preview.json", preview)
    selected = {f.get("path") for f in preview.get("files", [])}
    receipt["preview"] = {
        "rc": rc,
        "wall_seconds": wall,
        "timed_out": expired,
        "total_files": preview.get("total_files"),
        "reviewable_count": preview.get("reviewable_count"),
    }
    if rc or expired or selected != set(cases) or preview.get("reviewable_count") != 48:
        receipt["status"] = "failed_preview_scope"
        save(output / "receipt.json", receipt)
        return 1
    if not args.execute:
        receipt["status"] = "preview_only_48_verified"
        save(output / "receipt.json", receipt)
        return 0
    model_env, model, origin, redact = model_environment(ROOT, MODEL_TIMEOUT)
    environment.update(model_env)
    command += [
        "--model",
        model,
        "--concurrency",
        "3",
        "--timeout",
        "10",
        "--max-tokens-budget",
        str(TOKEN_CAP),
        "--background",
        BACKGROUND,
    ]
    receipt.update(
        status="running",
        command=command,
        model=model,
        endpoint_origin=origin,
    )
    save(output / "receipt.json", receipt)
    rc, stdout, stderr, wall, expired = invoke(command, environment, WALL_CAP, ROOT)
    stdout, stderr = redact(stdout), redact(stderr)
    (output / "stdout.txt").write_text(stdout)
    (output / "stderr.txt").write_text(stderr)
    data = {}
    try:
        data = json.loads(stdout)
        if not isinstance(data, dict):
            raise TypeError("Malformed OCR output")
        save(output / "raw.json", data)
        if not isinstance(data.get("comments"), list):
            raise TypeError("Missing OCR comments array")
        save(output / "parsed.json", parse_comments(data["comments"]))
    except (ValueError, TypeError):
        receipt["output_error"] = "Invalid or missing structured OCR output"
        if not isinstance(data, dict):
            data = {}
    session = native_session(scope, data, cases, redact, output)
    receipt.update(
        session=session,
        model_calls=session["llm_requests"],
        raw_status=data.get("status"),
        summary=data.get("summary"),
        tool_calls=data.get("tool_calls"),
        warnings=data.get("warnings"),
        retry_report=data.get("retry_report"),
        rc=rc,
        wall_seconds=wall,
        timed_out=expired,
    )
    complete = (
        not rc
        and not expired
        and "output_error" not in receipt
        and len(session["completed_paths"]) == 48
        and not session["failed_paths"]
        and session["llm_requests"] > 0
        and not session["malformed_records"]
    )
    receipt["status"] = "completed" if complete else "incomplete_unknown"
    receipt["scope_unchanged"] = all(
        hashlib.sha256((scope / path).read_bytes()).hexdigest() == digest
        for path, digest in hashes.items()
    )
    if not receipt["scope_unchanged"]:
        receipt["status"] = "invalid_source_changed"
    save(output / "receipt.json", json.loads(redact(json.dumps(receipt))))
    return 0 if receipt["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
