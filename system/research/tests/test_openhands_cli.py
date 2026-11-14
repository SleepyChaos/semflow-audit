"""OpenHands CLI run/inspect/cancel uses public core without platform imports."""

import json
import sys
from types import SimpleNamespace

from semflow_cli.main import main

from research.tests.openhands_cases import IMAGE, openhands_spec, proposal


def test_openhands_cli_run_and_inspect_without_app(
    research_case, settings, monkeypatch, capsys, tmp_path
):
    spec = openhands_spec(research_case)
    values = settings.model_dump(mode="json")
    values.update(OPENHANDS_PYTHON=sys.executable, OPENHANDS_IMAGE=IMAGE)
    values.pop("AI_BASE_URL", None)
    values.pop("AI_MODEL", None)
    values.pop("AI_API_KEY", None)
    values.pop("ARTIFACT_ROOT", None)
    resources = tmp_path / "resources.json"
    resources.write_text(
        json.dumps(
            {
                "profile_id": spec.policy.resource_profile,
                "settings": values,
                "model_endpoints": {
                    "scripted": {"base_url": "http://scripted.invalid"}
                },
            }
        )
    )
    # External boundaries only: the public CLI, runtime, graph, receipts and
    # codecs remain real. No app/FastAPI/Celery/SQLModel imports are present.
    monkeypatch.setattr(
        "semflow_research.repair.repair_openhands.generate",
        lambda *args, **kwargs: {
            "proposal": proposal(),
            "runtime": {"status": "completed", "metrics": {"calls": 1}},
        },
    )
    phases = []

    def create(**kwargs):
        payload = json.loads(kwargs["messages"][-1]["content"])[
            "untrusted_analysis_material"
        ]
        phases.append(payload["phase"])
        if payload["phase"] == "inspect_semantics":
            body = {
                "action": "ready",
                "project_overview": "Input source",
                "target_flow": "Input reaches eval",
                "modification_semantics": "Use integer conversion",
                "facts": [
                    {
                        "statement": "Source evaluates input",
                        "state": "supported",
                        "evidence_ids": [payload["evidence"][0]["id"]],
                        "category": "security",
                        "critical": True,
                    }
                ],
            }
        else:
            body = {
                "constraints": [
                    {
                        "fact_index": i,
                        "status": "consistent",
                        "explanation": "Explicit conversion",
                        "evidence_ids": [payload["evidence"][0]["id"]],
                    }
                    for i in payload["required_fact_indices"]
                ],
                "callers": [],
                "limitation": "Scripted model consistency is not executed exploitation evidence",
            }
        from openai.types.chat import ChatCompletion

        return ChatCompletion(
            id="cli",
            created=0,
            model="scripted",
            object="chat.completion",
            choices=[
                {
                    "index": 0,
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": json.dumps(body)},
                }
            ],
            usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        )

    monkeypatch.setattr(
        "semflow_research.repair.repair.validate_workspace",
        lambda *args, **kwargs: {
            "status": "passed",
            "profile": "syntax",
            "output": "scripted validator",
        },
    )
    monkeypatch.setattr(
        "semflow_research.adapters.ai.provider.OpenAI",
        lambda **kwargs: SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create)),
            base_url="http://scripted.invalid",
        ),
    )
    spec_path = tmp_path / "openhands.json"
    spec_path.write_text(spec.model_dump_json())
    assert (
        main(
            [
                "run",
                "--spec",
                str(spec_path),
                "--resources",
                str(resources),
                "--root",
                str(research_case.ledger.root),
            ]
        )
        == 0
    )
    output = json.loads(capsys.readouterr().out)
    assert output["execution_status"] == "completed"
    assert output["result"]["outcome"] == "checks_passed"
    assert phases == ["inspect_semantics", "assess_patch_contract"]
    assert (
        main(
            [
                "inspect",
                "--root",
                str(research_case.ledger.root),
                "--execution-id",
                str(spec.execution_id),
            ]
        )
        == 0
    )
    inspected = json.loads(capsys.readouterr().out)
    assert inspected["execution_status"] == "completed"
