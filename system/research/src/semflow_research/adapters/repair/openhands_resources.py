"""Resolve the exact frozen worker handoff and retain copied code identities."""

import hashlib
import shutil
from pathlib import Path

from semflow_contracts.errors import ResearchError

from semflow_research.evidence.context_materials import save_json


def worker_identity(settings):
    runner = (
        settings.OPENHANDS_RUNNER
        or Path(__file__).resolve().parents[2] / "engines/openhands/runner.py"
    )
    files = [
        runner.parent / name for name in ("runner.py", "container_tool.py", "budget.py")
    ]
    files.append(Path(__file__).with_name("bounded_process.py"))
    return {
        file.name: hashlib.sha256(file.read_bytes()).hexdigest()
        if file.is_file()
        else "missing"
        for file in files
    }


def worker_config(context, config):
    """Translate public field names exactly once; never consult live defaults."""
    same_endpoint = config["endpoint_profile"] == context.spec.model.endpoint_profile
    endpoint = context.settings.OPENHANDS_BASE_URL or (
        context.settings.AI_BASE_URL if same_endpoint else ""
    )
    if not endpoint:
        raise ResearchError(
            "model_unavailable", "Frozen OpenHands endpoint is unavailable"
        )
    return {
        **config,
        "image_id": config["image_digest"],
        "base_url": endpoint,
        "timeout": min(
            context.spec.policy.per_call_timeout_seconds, config["timeout_seconds"]
        ),
    }


def stage_worker(context, directory):
    python = Path(context.settings.OPENHANDS_PYTHON)
    runner = (
        context.settings.OPENHANDS_RUNNER
        or Path(__file__).resolve().parents[2] / "engines/openhands/runner.py"
    )
    if not python.is_file() or not runner.is_file():
        raise ResearchError(
            "tool_unavailable", "Pinned OpenHands runtime is not installed"
        )
    worker = directory / "worker-code"
    worker.mkdir()
    identities = {}
    for asset in ["runner.py", "container_tool.py", "budget.py"]:
        source = runner.parent / asset
        if not source.is_file():
            raise ResearchError(
                "tool_unavailable", "OpenHands worker asset is missing: " + asset
            )
        shutil.copyfile(source, worker / asset)
        identities[asset] = hashlib.sha256(source.read_bytes()).hexdigest()
    bounded = Path(__file__).with_name("bounded_process.py")
    shutil.copyfile(bounded, worker / "bounded_process.py")
    identities["bounded_process.py"] = hashlib.sha256(bounded.read_bytes()).hexdigest()
    if identities != context.settings.OPENHANDS_WORKER_IDENTITY:
        raise ResearchError(
            "integrity_error", "OpenHands worker bytes changed after resource freezing"
        )
    save_json(directory / "worker-identity.json", identities)
    return python, worker / "runner.py"
