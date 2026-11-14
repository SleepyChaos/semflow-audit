"""Freeze shipped OpenHands templates before an entry point starts an execution."""

from pathlib import Path

from semflow_contracts.errors import ResearchError
from semflow_contracts.runs import PromptSnapshot


def freeze_openhands_prompt(*, version: int, artifacts) -> PromptSnapshot:
    # WIRE-SEND:research.openhands — peer: repair.OpenHandsRepair.generate.
    # AGENT: template selection is input assembly; the receiver consumes this
    # exact reference and version, never reloads a package/platform default.
    path = (
        Path(__file__).resolve().parents[1] / f"prompts/repair-openhands.v{version}.txt"
    )
    if not path.is_file():
        raise ResearchError(
            "unsupported_version", "OpenHands Prompt version is unavailable"
        )
    ref = artifacts.commit(path.read_bytes(), kind="prompt", schema_version="prompt/1")
    return PromptSnapshot(
        role="repair_openhands",
        template_id="repair-openhands",
        version=str(version),
        content=ref,
        sha256=ref.sha256,
    )
