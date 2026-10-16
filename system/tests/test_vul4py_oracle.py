"""Reject absent tests and infrastructure errors before repair success scoring."""

from scripts.benchmarks.vul4py_oracle import dual_verdict, junit
from scripts.benchmarks.vul4py_oracle import test_pass as oracle_pass


def test_empty_or_skipped_functional_tests_never_pass(tmp_path):
    path = tmp_path / "empty.xml"
    path.write_text('<testsuites><testsuite tests="0"/></testsuites>')
    assert not oracle_pass(0, junit(path))
    path.write_text(
        "<testsuites><testsuite><testcase><skipped/></testcase></testsuite></testsuites>"
    )
    assert not oracle_pass(0, junit(path))
    path.write_text("<testsuites><testsuite><testcase/></testsuite></testsuites>")
    assert oracle_pass(0, junit(path))
    assert not oracle_pass(999, junit(path))


def test_dual_oracle_distinguishes_assertion_failure_from_import_error():
    ok = {"status": "parsed", "tests": 1, "failures": 0, "errors": 0, "skipped": 0}
    failed = {**ok, "failures": 1}
    rows = {
        "vulnerable": {"functional_rc": 0, "exploit_rc": 1},
        "fixed": {"functional_rc": 0, "exploit_rc": 0},
    }
    reports = {
        "vulnerable": {"functional": ok, "exploit": failed},
        "fixed": {"functional": ok, "exploit": ok},
    }
    assert dual_verdict(rows, reports)["accepted"]
    reports["vulnerable"]["exploit"] = {**failed, "errors": 1}
    assert not dual_verdict(rows, reports)["accepted"]
    reports["vulnerable"]["exploit"] = failed
    rows["fixed"]["functional_rc"] = 999
    assert not dual_verdict(rows, reports)["accepted"]
