"""Only stable, located candidate exceptions permit implementation feedback."""

from types import SimpleNamespace

from app.adapters.repair.verification_runner import parse_results
from app.services.repair_runtime_diagnosis import candidate_runtime_errors


def test_actual_junit_name_error_keeps_location(tmp_path):
    case = SimpleNamespace(name="test_security")
    suite = SimpleNamespace(cases=[case], language="python")
    xml = '<testsuite><testcase name="test_security"><failure message="NameError: missing symbol">app.py:2: NameError</failure></testcase></testsuite>'
    result = parse_results(xml, 1, suite)
    assert result["cases"]["test_security"]["status"] == "error"
    assert result["cases"]["test_security"]["exception_type"] == "NameError"
    assert result["cases"]["test_security"]["exception_line"] == 2
    (tmp_path / "app.py").write_text(
        "def calculate(value):\n    return missing(value)\n"
    )
    pairs = [{"after": result}] * 2
    assert (
        candidate_runtime_errors(suite, pairs, tmp_path)[0]["candidate_file"]
        == "app.py"
    )
    # A suite failure or dependency failure must not masquerade as candidate code.
    result["cases"]["test_security"]["exception_file"] = "/suite/test_check.py"
    assert candidate_runtime_errors(suite, pairs, tmp_path) == []
    result["cases"]["test_security"]["exception_file"] = "app.py"
    result["cases"]["test_security"]["exception_type"] = "ModuleNotFoundError"
    assert candidate_runtime_errors(suite, pairs, tmp_path) == []


def test_located_repeated_rejection_error_is_candidate_feedback(tmp_path):
    (tmp_path / "app.py").write_text(
        "def evaluate():\n    raise ValueError('unsupported expression')\n"
    )
    suite = SimpleNamespace(cases=[SimpleNamespace(name="test_security")])
    result = {
        "cases": {
            "test_security": {
                "status": "error",
                "exception_type": "ValueError",
                "exception_file": "app.py",
                "exception_line": 2,
                "exception_message": "ValueError: unsupported expression",
            }
        }
    }
    assert (
        candidate_runtime_errors(suite, [{"after": result}] * 2, tmp_path)[0][
            "exception_type"
        ]
        == "ValueError"
    )
