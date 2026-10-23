"""A batch interpretation cannot silently discard another selected request."""

from types import SimpleNamespace

import pytest
from app.domain.audit import AuditError
from app.services.repair_scope import complete_target_scope, missing_targets


def interpretation(citations):
    return {
        "view": {"facts": [{"state": "supported", "evidence_ids": citations}]},
        "evidence": [
            {
                "id": f"intent-{name}",
                "kind": "repair_request",
                "reference": {"candidate_id": name},
            }
            for name in ["first", "second"]
        ],
    }


def test_omitted_target_requires_complete_reinspection():
    targets = [{"id": "first"}, {"id": "second"}]
    calls = []

    def inspect(received, evidence, **arguments):
        calls.append(arguments)
        assert received == targets
        assert arguments["feedback"]["missing_repair_targets"] == [{"id": "second"}]
        return interpretation(["intent-first", "intent-second"])

    result = complete_target_scope(
        SimpleNamespace(inspect=inspect), interpretation(["intent-first"]), targets
    )
    assert missing_targets(result, targets) == []
    assert len(calls) == 1


def test_still_omitted_target_is_not_a_successful_batch():
    incomplete = interpretation(["intent-first"])
    with pytest.raises(AuditError, match="未覆盖全部"):
        complete_target_scope(
            SimpleNamespace(inspect=lambda *args, **kwargs: incomplete),
            incomplete,
            [{"id": "first"}, {"id": "second"}],
        )


def test_repair_format_recovery_keeps_the_previous_patch(monkeypatch):
    import json

    import httpx
    from app.contracts.stages import RepairResponse

    from tests.test_model_provider import completion, configured

    patch = {
        "summary": "按原始代码修改并保留正常数字转换行为",
        "changes": [
            {
                "file": "app.py",
                "old_text": "eval(value)",
                "new_text": "int(value)",
            }
        ],
    }
    requests = []

    def respond(request):
        messages = json.loads(request.content)["messages"]
        requests.append(messages)
        if len(requests) == 1:
            return httpx.Response(200, json=completion(json.dumps(patch)))
        assert json.loads(messages[-2]["content"]) == patch
        assert "reason" in messages[-1]["content"]
        corrected = json.loads(json.dumps(patch))
        corrected["changes"][0]["reason"] = "仅允许整数转换，避免动态执行用户表达式"
        return httpx.Response(200, json=completion(json.dumps(corrected)))

    provider = configured(monkeypatch, respond)
    result = provider.generate("repair", {"phase": "propose_patch"}, RepairResponse)
    assert result.changes[0].new_text == "int(value)"
    assert len(requests) == 2
