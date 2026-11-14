"""Isolated SDK process; secrets arrive on stdin and never enter the sandbox."""

import json
import os
import sys
import tempfile
import time
from importlib.metadata import version
from pathlib import Path

os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
os.environ["OTEL_SDK_DISABLED"] = "true"
os.environ["DO_NOT_TRACK"] = "1"

from budget import install
from container_tool import SandboxTool
from openhands.sdk import LLM, Agent, Conversation, Tool
from openhands.sdk.tool import register_tool
from pydantic import SecretStr


def save(path, data):
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str))
    temp.replace(path)


def run(config):
    directory = Path(config["directory"])
    if version("openhands-sdk") != config["sdk_version"]:
        raise RuntimeError("Installed OpenHands SDK differs from frozen version")
    install(
        LLM, directory, output_tokens=config["output_tokens"], timeout=config["timeout"]
    )
    events = []
    errors = []

    def observe(event):
        item = event.model_dump(mode="json")
        events.append(item)
        if item.get("kind") == "ConversationErrorEvent":
            errors.append(item.get("code"))
        with (directory / "events.jsonl").open("a") as stream:
            stream.write(json.dumps(item, ensure_ascii=False) + "\n")
        save(
            directory / "progress.json",
            {
                "events": len(events),
                "last_event_unix": time.time(),
                "last_event_type": type(event).__name__,
            },
        )

    model = config["model"]
    llm = LLM(
        model=model if "/" in model else "openai/" + model,
        api_key=SecretStr(config.pop("api_key")),
        base_url=config["base_url"],
        timeout=config["timeout"],
        num_retries=0,
        temperature=0,
        max_output_tokens=config["output_tokens"],
        max_input_tokens=64000,
        litellm_extra_body={"thinking": {"type": config["thinking"]}}
        if config.get("thinking")
        else {},
        usage_id="repair",
    )
    register_tool(SandboxTool.name, SandboxTool)
    agent = Agent(
        llm=llm,
        tools=[
            Tool(
                name=SandboxTool.name,
                params={
                    "container": config["container"],
                    "directory": str(directory),
                },
            )
        ],
    )
    started = time.monotonic()
    status, error = "completed", None
    conversation = None
    controller = tempfile.TemporaryDirectory(prefix="semflow-openhands-controller-")
    try:
        if version("openhands-sdk") != "1.56.0":
            raise RuntimeError("Installed OpenHands SDK differs from frozen version")
        conversation = Conversation(
            agent=agent,
            workspace=controller.name,
            persistence_dir=directory / "conversation",
            callbacks=[observe],
            max_iteration_per_run=config["max_steps"],
            visualizer=None,
            delete_on_close=False,
        )
        conversation.send_message(config["prompt"])
        conversation.run()
        state = str(conversation.state.execution_status)
        if "error" in state.lower() or "stuck" in state.lower():
            status, error = "failed", state
    except Exception as exc:  # noqa: BLE001 - terminal SDK boundary persists unknown failure
        status, error = "failed", type(exc).__name__
    finally:
        metrics = llm.metrics.model_dump(mode="json")
        save(
            directory / "runtime-result.json",
            {
                "status": status,
                "error_type": error,
                "error_code": errors[-1] if errors else None,
                "sdk_version": "1.56.0",
                "wall_seconds": time.monotonic() - started,
                "event_count": len(events),
                "metrics": metrics,
            },
        )
        if conversation is not None:
            conversation.close()
        controller.cleanup()
    return 0 if status == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(run(json.load(sys.stdin)))
