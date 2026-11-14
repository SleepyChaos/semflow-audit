"""Real pinned SDK resources with an explicit provider-only substitute."""

import os
import shutil
from pathlib import Path

SCRIPTED_PROVIDER = r"""
import json
from litellm.types.utils import ModelResponse
import openhands.sdk.llm.llm as llm_module
ordinal = 0
def scripted_completion(*args, **kwargs):
    global ordinal
    ordinal += 1
    tools = kwargs["tools"]
    if ordinal == 1:
        name = next(t["function"]["name"] for t in tools if "command" in t["function"]["parameters"].get("properties", {}))
        parameters = {"command": "python -c \"from pathlib import Path; p=Path('/workspace/app.py'); p.write_text(p.read_text().replace('eval(input())', 'int(input())'))\"", "timeout_seconds": 20}
    elif ordinal == 2:
        name = "finish"
        parameters = {"message": "Scripted numeric replacement delivered for independent validation"}
    else:
        raise RuntimeError("Unexpected model replay in real SDK gate")
    return ModelResponse(id="scripted-sdk-"+str(ordinal), model="scripted-agent", created=0,
        choices=[{"index":0,"finish_reason":"tool_calls","message":{"role":"assistant","content":"Apply only the authorized numeric change" if ordinal==1 else "Finish the candidate", "tool_calls":[{"id":"call-"+str(ordinal),"type":"function","function":{"name":name,"arguments":json.dumps(parameters)}}]}}],
        usage={"prompt_tokens":100,"completion_tokens":20,"total_tokens":120})
llm_module.litellm_completion = scripted_completion
"""


def sdk_resources(settings, tmp_path):
    assets = (
        Path(__file__).resolve().parents[1] / "src/semflow_research/engines/openhands"
    )
    worker = tmp_path / "scripted-provider-worker"
    worker.mkdir()
    original = (
        (assets / "runner.py")
        .read_text()
        .replace(
            "def save(path, data):", SCRIPTED_PROVIDER + "\n\ndef save(path, data):"
        )
    )
    (worker / "runner.py").write_text(original)
    for asset in ("container_tool.py", "budget.py"):
        shutil.copyfile(assets / asset, worker / asset)
    return settings.model_copy(
        update={
            "OPENHANDS_PYTHON": os.environ["SEMFLOW_OPENHANDS_SDK_PYTHON"],
            "OPENHANDS_IMAGE": os.environ["SEMFLOW_RESEARCH_VALIDATOR_IMAGE"],
            "OPENHANDS_RUNNER": worker / "runner.py",
            "VALIDATOR_PYTHON_IMAGE": os.environ["SEMFLOW_RESEARCH_VALIDATOR_IMAGE"],
        }
    )
