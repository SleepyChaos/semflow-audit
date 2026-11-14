"""Explicit external suite model/runner substitutes shared across integration gates."""

import json
from types import SimpleNamespace

import pytest
from openai.types.chat import ChatCompletion

IMAGE = "sha256:" + "a" * 64


@pytest.fixture
def suite_model(monkeypatch):
    calls = []

    def create(**kwargs):
        payload = json.loads(kwargs["messages"][-1]["content"])[
            "untrusted_analysis_material"
        ]
        calls.append(payload)
        targets = payload["required_candidate_ids"]
        body = {
            "title": "Numeric input policy",
            "summary": "Disallow expression evaluation and preserve numeric inputs",
            "language": "python",
            "files": {
                "test_numeric.py": "import pytest, runpy\n\ndef test_security(monkeypatch):\n    monkeypatch.setattr('builtins.input',lambda: '1+1')\n    with pytest.raises(ValueError): runpy.run_path('/workspace/app.py')\n\ndef test_functional(monkeypatch):\n    monkeypatch.setattr('builtins.input',lambda: '2')\n    assert runpy.run_path('/workspace/app.py')['value']==2\n"
            },
            "cases": [
                {
                    "name": "test_security",
                    "category": "security",
                    "candidate_ids": targets,
                    "input_description": "Expression input 1+1",
                    "expected_behavior": "Reject expression input with ValueError",
                },
                {
                    "name": "test_functional",
                    "category": "functional",
                    "candidate_ids": [],
                    "input_description": "Numeric input 2",
                    "expected_behavior": "Stored value is integer 2",
                },
            ],
            "assumptions": ["The selected application accepts integer inputs"],
        }
        return ChatCompletion(
            id="suite-test",
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
            usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        )

    factory = lambda **kwargs: SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create)),
        base_url="http://scripted.invalid/v1",
    )
    monkeypatch.setattr("semflow_research.adapters.ai.provider.OpenAI", factory)
    monkeypatch.setattr(
        "semflow_research.adapters.repair.verification_runner.resolve_image",
        lambda image: IMAGE,
    )
    return SimpleNamespace(calls=calls, factory=factory)


@pytest.fixture
def suite_runner(monkeypatch):
    from semflow_research.adapters.repair.verification_runner import parse_results

    observed = []

    def run(workspace, tests, suite, image, directory, *, _kernel):
        directory.mkdir(parents=True)
        assert (tests / "test_numeric.py").read_text() == suite.files["test_numeric.py"]
        text = (workspace / "app.py").read_text()
        observed.append(text)
        failure = (
            '<failure message="AssertionError: expression was accepted"/>'
            if "eval(" in text
            else ""
        )
        xml = (
            '<testsuite><testcase name="test_security">'
            + failure
            + '</testcase><testcase name="test_functional"/></testsuite>'
        )
        return {**parse_results(xml, 1 if failure else 0, suite), "image_id": image}

    monkeypatch.setattr(
        "semflow_research.repair.repair_suite_checks.resolve_image", lambda image: IMAGE
    )
    monkeypatch.setattr("semflow_research.repair.repair_suite_checks.run_suite", run)
    monkeypatch.setattr("semflow_research.runtime.repair_verify.run_suite", run)
    monkeypatch.setattr(
        "semflow_research.runtime.repair_verify.resolve_image", lambda image: IMAGE
    )
    return observed
