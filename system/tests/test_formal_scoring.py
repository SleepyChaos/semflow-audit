"""Wrong CWE, duplicate reports and incomplete labels must not inflate scores."""

from scripts.benchmarks.formal_inputs import synchronize_case_loader
from scripts.benchmarks.formal_loader_correction import loader_prefix
from scripts.benchmarks.formal_scoring import score_cases


def test_duplicates_count_one_case_and_wrong_weakness_does_not_match():
    labels = [
        {"task_id": "a", "file": "testcode/a.py", "vulnerable": True, "cwe": 89},
        {"task_id": "b", "file": "testcode/b.py", "vulnerable": False, "cwe": 89},
        {"task_id": "c", "file": "testcode/c.py", "vulnerable": True, "cwe": 22},
    ]

    def finding(identifier, file, cwe):
        return {
            "id": identifier,
            "tags": [f"external/cwe/cwe-{cwe:03}"],
            "locations": [{"file": f"/source/testcode/{file}.py", "line": 1}],
        }

    result = score_cases(
        labels,
        [
            finding("one", "a", 89),
            finding("dup", "a", 89),
            finding("wrong", "c", 89),
            finding("negative", "b", 89),
        ],
    )
    assert result["counts"] == {"TP": 1, "FP": 1, "TN": 0, "FN": 1}
    assert result["outside_target_alerts"] == ["wrong"]


def test_empty_success_has_no_precision_and_unknown_alert_is_not_false_positive():
    label = {"task_id": "a", "file": "a.py", "vulnerable": False, "cwe": 89}
    result = score_cases(
        [label],
        [{"id": "unknown", "locations": [{"file": "helper.py"}], "weakness": "CWE-89"}],
    )
    assert result["counts"] == {"TP": 0, "FP": 0, "TN": 1, "FN": 0}
    assert result["precision"] is None
    assert result["outside_target_alerts"] == ["unknown"]


def test_anonymized_loader_must_register_same_case_set():
    body = "files = filter(lambda file: file.startswith('Benchmark'), names)"
    names = ["Case001.py", "Case002.py", "__init__.py"]
    assert not [n for n in names if n.startswith(loader_prefix(body))]
    corrected = synchronize_case_loader(body)
    assert [n for n in names if n.startswith(loader_prefix(corrected))] == [
        "Case001.py",
        "Case002.py",
    ]
