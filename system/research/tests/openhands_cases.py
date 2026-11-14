"""Shared OpenHands contract and scripted candidate fixtures."""

from research.tests.native_cases import repair_spec

IMAGE = "sha256:" + "b" * 64


def openhands_spec(case):
    value = repair_spec(case).model_dump(mode="json")
    value["inputs"]["engine"] = "openhands"
    value["inputs"]["openhands"] = {
        "sdk_version": "1.56.0",
        "image_digest": IMAGE,
        "model": "scripted-agent",
        "endpoint_profile": "scripted",
        "prompt_version": 3,
        "max_steps": 4,
        "timeout_seconds": 30,
        "output_tokens": 2000,
    }
    value["policy"]["max_attempts"] = 1
    value["implementation"]["method_version"] = "4"
    from semflow_contracts.runs import validate_spec
    from semflow_research.public.prompts import freeze_openhands_prompt

    prompt = freeze_openhands_prompt(version=3, artifacts=case.artifacts)
    value["prompts"].append(prompt.model_dump(mode="json"))
    return validate_spec(value)


def proposal():
    return {
        "changes": [
            {
                "file": "app.py",
                "old_text": "eval(input())",
                "new_text": "int(input())",
                "reason": "Replace dynamic evaluation with explicit integer conversion",
            }
        ],
        "summary": "OpenHands selected explicit integer conversion for the frozen target",
    }
