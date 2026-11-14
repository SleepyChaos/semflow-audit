"""OpenHands tool executing only inside one pre-created, networkless container."""

import json
import os
import time
from pathlib import Path

from app.adapters.repair.bounded_process import execute_bounded
from openhands.sdk import Action, Observation, TextContent, ToolDefinition
from openhands.sdk.tool import ToolExecutor
from pydantic import Field


class SandboxAction(Action):
    command: str = Field(min_length=1, max_length=16000)
    timeout_seconds: int = Field(default=60, ge=1, le=120)


class SandboxObservation(Observation):
    output: str
    exit_code: int | None
    reason: str | None = None

    @property
    def to_llm_content(self):
        return [TextContent(text=json.dumps(self.model_dump(), ensure_ascii=False))]


class SandboxExecutor(ToolExecutor[SandboxAction, SandboxObservation]):
    def __init__(self, container, directory):
        self.container, self.directory = container, Path(directory)
        self.ordinal = 0

    def __call__(self, action, conversation=None):
        self.ordinal += 1
        args = [
            "docker",
            "exec",
            "--workdir",
            "/workspace",
            self.container,
            "timeout",
            "--signal=TERM",
            "--kill-after=5",
            str(action.timeout_seconds),
            "/bin/bash",
            "-o",
            "pipefail",
            "-c",
            action.command,
        ]
        result = execute_bounded(
            args,
            action.timeout_seconds + 15,
            {
                k: v
                for k, v in os.environ.items()
                if k in {"PATH", "HOME", "DOCKER_HOST", "DOCKER_CONTEXT"}
            },
            output_limit=1_000_000,
            tail_limit=16000,
        )
        if result["exit_code"] == 124 and not result["reason"]:
            result["reason"] = (
                f"Exit 124 may indicate timeout; this tool limits the command to {action.timeout_seconds}s. "
                "This is not a passing test verdict. Choose focused tests instead of repeating an overlong suite."
            )
        receipt = {
            "ordinal": self.ordinal,
            "command": action.command,
            "finished_unix": time.time(),
            **result,
        }
        (self.directory / f"tool-{self.ordinal}.json").write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2)
        )
        return SandboxObservation(
            output=result["output"],
            exit_code=result["exit_code"],
            reason=result["reason"],
        )


class SandboxTool(ToolDefinition[SandboxAction, SandboxObservation]):
    @classmethod
    def create(cls, conv_state, container, directory):
        return [
            cls(
                description=(
                    "Run a bash command inside the isolated project workspace /workspace. "
                    "Use this to inspect source, edit authorized existing files with Python, and run existing "
                    "project/development tests. No network, hidden tests, git history or host "
                    "filesystem is available. Edits outside authorized source files will be rejected. "
                    "Use bounded commands; output is limited."
                ),
                action_type=SandboxAction,
                observation_type=SandboxObservation,
                executor=SandboxExecutor(container, directory),
            )
        ]
