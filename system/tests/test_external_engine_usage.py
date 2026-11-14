"""SDK accounting never mutates native budgets or guesses missing consumption."""

import json

from app.adapters.ai.external_usage import combined_usage


def test_native_engine_without_external_receipt_is_unchanged(tmp_path):
    native = {"calls": 2, "input_tokens": 100, "output_tokens": 30}
    assert combined_usage(native, tmp_path) == native


def test_completed_sdk_calls_are_counted_once_and_keep_native_breakdown(tmp_path):
    native = {"calls": 2, "input_tokens": 100, "output_tokens": 30}
    folder = tmp_path / "openhands"
    folder.mkdir()
    receipt = {
        "status": "completed",
        "metrics": {
            "token_usages": [{}, {}, {}],
            "accumulated_token_usage": {"prompt_tokens": 400, "completion_tokens": 60},
        },
    }
    (folder / "runtime-result.json").write_text(json.dumps(receipt))
    value = combined_usage(native, tmp_path)
    assert (value["calls"], value["input_tokens"], value["output_tokens"]) == (
        5,
        500,
        90,
    )
    assert native == {"calls": 2, "input_tokens": 100, "output_tokens": 30}
    assert value["native"] == native and not value["known_usage_only"]
    assert value == combined_usage(native, tmp_path)
    assert value == combined_usage(value, tmp_path)
    assert value["external_engines"]["openhands"]["provider_cost_usd"] is None


def test_missing_and_corrupt_sdk_receipt_retain_unknown_instead_of_zero(tmp_path):
    folder = tmp_path / "openhands"
    folder.mkdir()
    for contents in (None, "{"):
        if contents:
            (folder / "runtime-result.json").write_text(contents)
        value = combined_usage({"calls": 2}, tmp_path)
        assert value["calls"] == 2 and value["known_usage_only"]
        assert value["external_engines"]["openhands"]["calls"] is None
