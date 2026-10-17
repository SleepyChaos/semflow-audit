from uuid import uuid4

import pytest
from app.adapters.repair.verification_runner import parse_results
from app.contracts.verification import VerificationSuite
from app.services.verification_results import compare_runs


def spec():
    target = str(uuid4())
    return VerificationSuite.model_validate(
        {
            "title": "动态执行的功能与安全检查",
            "summary": "同一输入在原始代码和补丁副本中运行，核对功能保持和不可信代码阻断。",
            "language": "python",
            "files": {
                "test_verification.py": "def test_security():\n    assert True\ndef test_normal():\n    assert True\n"
            },
            "cases": [
                {
                    "name": "test_security",
                    "category": "security",
                    "candidate_ids": [target],
                    "input_description": "不可信代码输入",
                    "expected_behavior": "输入不得执行代码",
                },
                {
                    "name": "test_normal",
                    "category": "functional",
                    "candidate_ids": [],
                    "input_description": "正常业务输入",
                    "expected_behavior": "业务结果仍然正确",
                },
            ],
            "assumptions": ["测试断言需要人工审阅"],
        }
    )


def run(security="assertion_failed", normal="passed"):
    return {
        "status": "completed",
        "cases": {
            "test_security": {"status": security},
            "test_normal": {"status": normal},
        },
    }


def test_same_security_case_must_reproduce_before_and_pass_after():
    suite = spec()
    result = compare_runs(
        suite, [{"before": run(), "after": run("passed")} for _ in range(2)]
    )
    assert result["status"] == "passed"
    assert result["cases"][0]["before"] == "assertion_failed"
    assert result["cases"][0]["after"] == "passed"
    all_green = compare_runs(
        suite, [{"before": run("passed"), "after": run("passed")} for _ in range(2)]
    )
    assert all_green["status"] == "inconclusive"


@pytest.mark.parametrize(
    "before,after,expected",
    [
        ("error", "passed", "inconclusive"),
        ("skipped", "passed", "inconclusive"),
        ("assertion_failed", "assertion_failed", "failed"),
    ],
)
def test_errors_skips_and_still_triggered_vulnerability_do_not_pass(
    before, after, expected
):
    result = compare_runs(
        spec(), [{"before": run(before), "after": run(after)} for _ in range(2)]
    )
    assert result["status"] == expected


def test_functional_regression_or_inconsistent_runs_prevent_acceptance():
    result = compare_runs(
        spec(),
        [
            {"before": run(), "after": run("passed", "assertion_failed")}
            for _ in range(2)
        ],
    )
    assert result["status"] == "failed"
    flaky = compare_runs(
        spec(),
        [
            {"before": run(), "after": run("passed")},
            {"before": run("passed"), "after": run("passed")},
        ],
    )
    assert flaky["status"] == "inconclusive"


def test_junit_import_failure_and_assertion_failure_are_different():
    xml = '<testsuites><testsuite><testcase name="test_security"><failure message="AssertionError: raw HTML"/></testcase><testcase name="test_normal"/></testsuite></testsuites>'
    result = parse_results(xml, 1, spec())
    assert result["cases"]["test_security"]["status"] == "assertion_failed"
    assert result["cases"]["test_normal"]["status"] == "passed"
    broken = parse_results(
        xml.replace(
            'failure message="AssertionError: raw HTML"',
            'error message="ModuleNotFoundError"',
        ),
        1,
        spec(),
    )
    assert broken["cases"]["test_security"]["status"] == "error"


def test_suite_cannot_write_outside_tests_or_omit_normal_behavior():
    suite = spec().model_dump(mode="json")
    suite["files"] = {"../app.py": "pass"}
    with pytest.raises(ValueError):
        VerificationSuite.model_validate(suite)
    suite = spec().model_dump(mode="json")
    suite["cases"] = suite["cases"][:1]
    with pytest.raises(ValueError):
        VerificationSuite.model_validate(suite)


def test_generated_python_syntax_errors_reach_model_validation_before_freezing():
    suite = spec().model_dump(mode="json")
    suite["files"]["test_verification.py"] = (
        "def test_security():\n    assert True\n  assert False\n"
    )
    with pytest.raises(ValueError, match="test_verification.py:3"):
        VerificationSuite.model_validate(suite)
    suite["files"]["test_verification.py"] = (
        "def test_security():\n    assert True\ndef test_normal():\n    assert True\n"
    )
    assert VerificationSuite.model_validate(suite).cases[0].name == "test_security"


@pytest.mark.parametrize(
    "message",
    [
        "ValueError: invalid AssertionError policy",
        "ModuleNotFoundError: ERR_ASSERTION",
        "RuntimeError: assert expected",
    ],
)
def test_exception_message_cannot_impersonate_a_security_assertion(message):
    xml = f'<testsuites><testsuite><testcase name="test_security"><failure message="{message}">AssertionError in source text</failure></testcase><testcase name="test_normal"/></testsuite></testsuites>'
    result = parse_results(xml, 1, spec())
    assert result["cases"]["test_security"]["status"] == "error"
    assert (
        compare_runs(
            spec(), [{"before": result, "after": run("passed")} for _ in range(2)]
        )["status"]
        == "inconclusive"
    )


def test_pytest_rejected_exception_assertion_is_an_actual_failure():
    xml = '<testsuites><testsuite><testcase name="test_security"><failure message="Failed: DID NOT RAISE ValueError"/></testcase><testcase name="test_normal"/></testsuite></testsuites>'
    assert (
        parse_results(xml, 1, spec())["cases"]["test_security"]["status"]
        == "assertion_failed"
    )


def test_node_structured_exception_type_does_not_trust_stack_text():
    suite = spec().model_dump(mode="json")
    suite["language"] = "javascript"
    suite["files"] = {"check.test.cjs": "// Test report parser fixture"}
    suite = VerificationSuite.model_validate(suite)
    xml = '<testsuites><testsuite><testcase name="test_security"><failure type="ExecutionError" message="AssertionError [ERR_ASSERTION]">cause: AssertionError [ERR_ASSERTION]</failure></testcase><testcase name="test_normal"/></testsuite></testsuites>'
    assert parse_results(xml, 1, suite)["cases"]["test_security"]["status"] == "error"
    assert (
        parse_results(
            xml.replace('type="ExecutionError"', 'type="AssertionError"'), 1, suite
        )["cases"]["test_security"]["status"]
        == "assertion_failed"
    )


def test_container_client_bounds_output_during_execution():
    import os
    import sys

    from app.adapters.repair.bounded_process import TAIL_LIMIT, execute_bounded

    result = execute_bounded(
        [sys.executable, "-c", "import sys; sys.stdout.write('x' * 3000000)"],
        10,
        dict(os.environ),
    )
    assert "输出超过限制" in result["reason"]
    assert len(result["output"]) <= TAIL_LIMIT
    failed = execute_bounded(
        [sys.executable, "-c", "import sys; print('real failure'); sys.exit(1)"],
        10,
        dict(os.environ),
    )
    assert failed["exit_code"] == 1 and failed["reason"] is None
    assert "real failure" in failed["output"]


def test_isolated_report_reader_ignores_uploaded_startup_hook(tmp_path):
    import os
    import sys

    from app.adapters.repair.bounded_process import execute_bounded

    (tmp_path / "sitecustomize.py").write_text(
        "print('untrusted startup output')\n", encoding="utf-8"
    )
    env = {**os.environ, "PYTHONPATH": str(tmp_path)}
    result = execute_bounded(
        [sys.executable, "-I", "-S", "-c", "print('<report/>')"],
        10,
        env,
        tail_limit=2000000,
    )
    assert result["reason"] is None
    assert result["output"].strip() == "<report/>"
