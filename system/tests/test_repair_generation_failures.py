"""Regression cases from a 13-target repair and transient provider connections."""

import json

import httpx
import pytest
from app.contracts.stages import RepairResponse, ReviewResponse
from app.domain.audit import AuditError

from tests.test_model_provider import completion, configured


def test_batch_patch_keeps_all_eleven_source_edits(monkeypatch):
    patch = {
        "summary": "修复多个已确认的漏洞，保留每一处原始代码修改",
        "changes": [
            {
                "file": "app.py",
                "old_text": f"unsafe_{i}(value)",
                "new_text": f"safe_{i}(value)",
                "reason": "替换当前漏洞对应的不安全操作，保留正常功能",
            }
            for i in range(11)
        ],
    }
    provider = configured(
        monkeypatch, lambda _: httpx.Response(200, json=completion(json.dumps(patch)))
    )
    result = provider.generate("repair", {}, RepairResponse)
    assert result.model_dump() == patch
    assert len(provider.records) == 1


@pytest.mark.parametrize("recover", [True, False])
def test_connection_retries_are_bounded_and_recorded(monkeypatch, recover):
    calls, waits = [], []
    monkeypatch.setattr("app.adapters.ai.provider.sleep", waits.append)

    def handler(request):
        calls.append(request)
        if len(calls) <= 3 or not recover:
            raise httpx.ConnectError("temporary connection failure", request=request)
        return httpx.Response(
            200, json=completion('{"action":"final","summary":"证据不足"}')
        )

    provider = configured(monkeypatch, handler)
    if recover:
        assert provider.generate("review", {}, ReviewResponse).action == "final"
    else:
        with pytest.raises(AuditError, match="连接暂时失败") as error:
            provider.generate("review", {}, ReviewResponse)
        assert error.value.code == "connection_error"
    assert len(calls) == len(provider.records) == 4
    assert waits == [2, 4, 8]
    assert all(row["error_code"] == "connection_error" for row in provider.records[:3])


def test_authentication_failure_is_not_retried(monkeypatch):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(401, json={"error": {"message": "invalid key"}})

    provider = configured(monkeypatch, handler)
    with pytest.raises(AuditError):
        provider.generate("review", {}, ReviewResponse)
    assert len(calls) == 1
