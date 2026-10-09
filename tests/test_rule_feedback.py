"""Retry context keeps actual errors, candidate code and exact counterexamples."""

from app.services.rule_feedback import compact_feedback, diagnostic_view


def test_compiler_view_retains_every_error_and_context_without_pack_chatter():
    raw = {
        "message": "Compile failed",
        "code": "compiler_error",
        "log_tail": "\n".join(
            ["Resolving installed dependency" * 40] * 20
            + [
                "candidate.qll:3",
                "ERROR: Could not resolve getACall",
                "  unknown method on Node",
                "ERROR: Incompatible class",
                "  previous_source",
            ]
        ),
    }
    view = diagnostic_view(raw, "draft-0/diagnostic.json")
    assert "ERROR: Could not resolve getACall" in view["log_tail"]
    assert "ERROR: Incompatible class" in view["log_tail"]
    assert "unknown method on Node" in view["log_tail"]
    assert len(view["log_tail"]) < 200
    assert len(raw["log_tail"]) > 10000


def test_unknown_diagnostic_is_not_silently_omitted():
    raw = {
        "message": "Execution failed",
        "log_tail": "unrecognized tool output\nwith important details",
    }
    assert diagnostic_view(raw, "original.json")["log_tail"] == raw["log_tail"]


def test_feedback_keeps_safe_false_positive_and_missing_root_locations():
    previous = {
        "query": "the full QL query",
        "modules": {"Source.qll": "the full model"},
        "positive": {"files": {"v.py": "eval(input())"}},
    }
    context = {
        "previous_candidate": previous,
        "development_feedback": {
            "status": "failed",
            "tests": {
                "positive": {
                    "status": "failed",
                    "expected": [["v.py", 3]],
                    "actual": [],
                    "snapshot_hash": "positive-source",
                    "findings": [],
                },
                "negative": {
                    "status": "failed",
                    "expected": [],
                    "actual": [["safe.py", 4]],
                    "snapshot_hash": "safe-source",
                    "findings": [{"code_flows": "verbose paths"}],
                },
            },
        },
    }
    compact = compact_feedback(context, "draft-0")
    assert compact["previous_candidate"] is previous
    assert compact["development_feedback"]["tests"]["negative"]["actual"] == [
        ["safe.py", 4]
    ]
    assert compact["development_feedback"]["tests"]["positive"]["expected"] == [
        ["v.py", 3]
    ]
    assert "findings" not in compact["development_feedback"]["tests"]["negative"]
    assert "findings" in context["development_feedback"]["tests"]["negative"]
