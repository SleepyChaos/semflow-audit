"""Read non-secret version evidence without importing the application or running tests."""

import ast
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import subprocess
import sys
from pathlib import Path

import tomllib
import yaml
from dotenv import dotenv_values


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def command(args, root):
    try:
        result = subprocess.run(
            args, cwd=root, capture_output=True, text=True, timeout=25, check=False
        )
        return {
            "status": "observed" if result.returncode == 0 else "unavailable",
            "exit_code": result.returncode,
            "value": result.stdout.strip() if result.returncode == 0 else None,
        }
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"status": "unavailable", "reason": type(exc).__name__, "value": None}


SAFE_SETTINGS = {
    "CODEQL_BIN",
    "CODEQL_PYTHON_BIN",
    "CODEQL_THREADS",
    "CODEQL_RAM",
    "PYTHON_QUERY_PACK",
    "JAVASCRIPT_QUERY_PACK",
    "SCAN_TIMEOUT",
    "AI_MODEL",
    "AI_TIMEOUT",
    "AI_MAX_OUTPUT_TOKENS",
    "AI_REVIEW_TOKENS",
    "AI_SCOUT_TOKENS",
    "AI_REPAIR_TOKENS",
    "AI_RULE_TOKENS",
    "AI_THINKING_MODE",
    "AI_STAGE_MAX_CALLS",
    "AI_STAGE_MAX_TOKENS",
    "AI_STAGE_MAX_SECONDS",
    "EMBEDDING_MODEL",
    "EMBEDDING_REVISION",
    "EMBEDDING_DIMENSIONS",
    "SEMANTIC_CONTEXT_CHARS",
    "SEMANTIC_TOOL_LIMIT",
    "REPAIR_ATTEMPTS",
    "VALIDATOR_PYTHON_IMAGE",
    "VALIDATOR_JS_IMAGE",
    "VALIDATOR_TIMEOUT",
}


def configuration(root):
    tree = ast.parse((root / "system/backend/app/core/audit_config.py").read_text())
    values, sources = {}, {}
    for node in ast.walk(tree):
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            key = node.target.id
            if key in SAFE_SETTINGS:
                values[key] = ast.literal_eval(node.value)
                sources[key] = "source_default"
    env_path = root / ".env"
    # Only allowlisted values leave this function; never copy or hash .env.
    if env_path.is_file():
        for key, value in dotenv_values(env_path, interpolate=False).items():
            if key in SAFE_SETTINGS and value is not None:
                values[key] = value
                sources[key] = "local_dotenv"
    for key in SAFE_SETTINGS & os.environ.keys():
        values[key], sources[key] = os.environ[key], "archive_process_environment"
    return {
        "values": values,
        "sources": sources,
        "scope": "Archive process configuration; not a probe of running API/Worker",
    }


def environment(root, *, inspect_images=True):
    config = configuration(root)
    locks = [
        "system/uv.lock",
        "system/frontend/package-lock.json",
        "system/scripts/tools/codeql-lsp/package-lock.json",
    ]
    packages = sorted(
        {
            f"{d.metadata['Name']}=={d.version}"
            for d in importlib.metadata.distributions()
        }
    )
    lock = tomllib.loads((root / "system/uv.lock").read_text())
    npm_lock = json.loads((root / "system/frontend/package-lock.json").read_text())
    observed_npm = {}
    for name in ("react", "vite", "typescript", "@playwright/test"):
        path = root / "system/frontend/node_modules" / name / "package.json"
        observed_npm[name] = (
            json.loads(path.read_text())["version"] if path.is_file() else None
        )
    stage_tree = ast.parse((root / "system/backend/app/api/routes/stages.py").read_text())
    defaults = next(
        ast.literal_eval(node)
        for node in ast.walk(stage_tree)
        if isinstance(node, ast.Dict)
        and {k.value for k in node.keys if isinstance(k, ast.Constant)}
        == {"review", "repair", "rule", "scout"}
    )
    commands = {
        "git": ["git", "--version"],
        "uv": ["uv", "--version"],
        "node": ["node", "--version"],
        "npm": ["npm", "--version"],
        "docker": ["docker", "--version"],
        "codeql": [str(config["values"]["CODEQL_BIN"]), "version", "--format=json"],
        "codeql_extractor_python": [
            str(config["values"]["CODEQL_PYTHON_BIN"]),
            "--version",
        ],
    }
    compose = yaml.safe_load((root / "system/compose.yml").read_text())
    images = {
        name: service["image"]
        for name, service in compose["services"].items()
        if "image" in service
    }
    images.update(
        {
            "python_validator": str(config["values"]["VALIDATOR_PYTHON_IMAGE"]),
            "javascript_validator": str(config["values"]["VALIDATOR_JS_IMAGE"]),
        }
    )
    image_identities = {
        name: command(
            [
                "docker",
                "image",
                "inspect",
                "--format",
                "{{json .Id}} {{json .RepoDigests}} {{json .Architecture}}",
                tag,
            ],
            root,
        )
        if inspect_images
        else {
            "status": "not_observed",
            "reason": "offline_archive_no_service_access",
            "value": None,
        }
        for name, tag in images.items()
    }
    return {
        "scope": "Current archive-time observation; never inherited by historical results",
        "platform": platform.platform(),
        "architecture": platform.machine(),
        "python": sys.version,
        "python_executable": str(Path(sys.executable).absolute()),
        "installed_python_packages": packages,
        "configuration": config,
        "commands": {name: command(args, root) for name, args in commands.items()},
        "dependency_locks": {name: sha256(root / name) for name in locks},
        "locked_python_packages": [
            {"name": p["name"], "version": p.get("version")} for p in lock["package"]
        ],
        "locked_frontend_packages": {
            name: p.get("version")
            for name, p in npm_lock["packages"].items()
            if name and p.get("version")
        },
        "observed_frontend_packages": observed_npm,
        "stage_defaults_from_source": defaults,
        "prompt_files": {
            p.relative_to(root).as_posix(): sha256(p)
            for p in sorted((root / "system/backend/app/prompts").glob("*.txt"))
        },
        "compose_sha256": sha256(root / "system/compose.yml"),
        "service_images": images,
        "service_image_identities": image_identities,
        "service_image_scope": "Local image store, not a claim about currently running containers",
        "corpus_status": "not_queried; use historical corpus receipts, not the current DB",
        "secret_content_archived": False,
    }


SCALAR_KEYS = {
    "experiment_id",
    "run_id",
    "git_head",
    "baseline_commit",
    "commit",
    "version",
    "prompt_version",
    "scout_version",
    "review_version",
    "final_version",
    "codeql_version",
    "codeql_cli",
    "cli",
    "model",
    "response_model",
    "actual_smoke_model",
    "thinking_mode",
    "embedding_model",
    "embedding_revision",
    "dataset_hash",
    "corpus_hash",
    "snapshot",
    "source_sha256",
    "query_hash",
    "input_manifest_sha256",
    "scorer_sha256",
    "working_tree_content_hash",
    "evaluator_version",
    "seed",
    "temperature",
    "query_pack",
    "pack",
    "date",
    "python",
    "javascript",
    "ram_mb",
    "threads",
    "ram",
    "calls",
    "tokens",
    "seconds",
    "max_calls",
    "max_tokens",
    "max_seconds",
    "rule_tokens",
    "max_output_tokens",
    "suite",
    "suite_sha256",
    "content_hash",
}
HASH_MAP_KEYS = {
    "implementation_hashes",
    "production_hashes",
    "hashes",
    "prompt_hashes",
}


def evidence(value):
    """Extract only explicit version evidence; arbitrary report prose stays local."""
    found, maps = {}, {}

    def walk(item, prefix=""):
        if isinstance(item, dict):
            for key, child in item.items():
                location = f"{prefix}.{key}" if prefix else key
                if key in HASH_MAP_KEYS and isinstance(child, dict):
                    valid = {
                        k: v
                        for k, v in child.items()
                        if isinstance(v, str) and re.fullmatch(r"[0-9a-f]{64}", v)
                    }
                    if valid:
                        maps[location] = {
                            "files": len(valid),
                            "map_sha256": digest(valid),
                        }
                    continue
                if key == "prompt_versions" and isinstance(child, dict):
                    for stage, version in child.items():
                        if stage in {"scout", "review", "rule", "repair"}:
                            found[f"{location}.{stage}"] = str(version)
                elif key in SCALAR_KEYS and isinstance(child, (str, int, float, bool)):
                    if not isinstance(child, str) or (
                        len(child) < 180 and "\n" not in child and "://" not in child
                    ):
                        found[location] = child
                elif key in {"response_models", "actual_models"} and isinstance(
                    child, list
                ):
                    found[location] = [
                        x for x in child if isinstance(x, str) and len(x) < 100
                    ]
                walk(child, location)
        elif isinstance(item, list):
            for i, child in enumerate(item):
                walk(child, f"{prefix}[{i}]")

    walk(value)
    return {"declared": found, "hash_maps": maps}
