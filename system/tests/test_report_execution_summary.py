def test_report_overview_summarizes_repeated_logs_but_preserves_failed_and_uncertain_results():
    import json
    from copy import deepcopy

    from app.services.report_overview import overview_material

    data = {
        "audit": {},
        "summary": {},
        "coverage": {},
        "candidates": [],
        "review_context": [],
        "repairs": [],
        "verification": [],
        "rules": [],
        "stages": [],
    }
    data["repairs"] = [
        {
            "id": "patch",
            "changes": [],
            "validation": {
                "rescan": {
                    "status": "needs_review",
                    "findings": [
                        {
                            "rule": "py/code-injection",
                            "code_flows": ["raw SARIF" * 5000],
                        }
                    ],
                    "remaining_target_rules": ["py/code-injection"],
                },
                "isolated_tests": {"status": "passed", "profile": "syntax"},
            },
        }
    ]
    data["verification"] = [
        {
            "repair_id": "patch",
            "comparison": {
                "status": "inconclusive",
                "repetitions": 2,
                "cases": [
                    {
                        "category": "security",
                        "before": "assertion_failed",
                        "after": "assertion_failed",
                        "reason": "安全断言仍未通过",
                        "stable": True,
                    },
                    {
                        "category": "security",
                        "before": "passed",
                        "after": "passed",
                        "reason": "原始代码未复现漏洞",
                        "stable": True,
                    },
                    {
                        "category": "functional",
                        "before": "passed",
                        "after": "passed",
                        "reason": "正常功能保持",
                        "stable": True,
                    },
                ],
                "runs": [{"stdout": "repeated test output" * 20000} for _ in range(4)],
            },
        }
    ]
    before = deepcopy(data)
    overview = overview_material(data)
    assert len(json.dumps(overview, ensure_ascii=False).encode()) < 6000
    checks = overview["repairs"][0]["validation"]
    assert checks["rescan"]["status"] == "needs_review"
    assert checks["rescan"]["findings_count"] == 1
    assert checks["rescan"]["remaining_target_rules"] == ["py/code-injection"]
    comparison = overview["verification"][0]["comparison"]
    assert comparison["status"] == "inconclusive"
    assert comparison["case_count"] == 3 and comparison["run_count"] == 4
    assert sum(row["count"] for row in comparison["case_results"]) == 3
    assert {row["reason"] for row in comparison["reasons"]} == {
        "安全断言仍未通过",
        "原始代码未复现漏洞",
        "正常功能保持",
    }
    assert "runs" not in comparison and data == before

    data["rules"] = [
        {
            "id": "baseline",
            "status": "validated",
            "validation": {
                "status": "passed",
                "tests": {
                    "positive": {
                        "status": "passed",
                        "findings": [{"code_flows": ["raw SARIF" * 10000]}],
                    }
                },
                "independent_holdout": {
                    "status": "failed",
                    "tests": {
                        "negative": {"status": "failed", "findings": ["log" * 10000]},
                    },
                },
            },
        }
    ]
    overview = overview_material(data)
    assert len(json.dumps(overview, ensure_ascii=False).encode()) < 7000
    rule = overview["rules"][0]["validation"]
    assert rule["status"] == "passed"
    assert rule["tests"]["positive"]["status"] == "passed"
    assert rule["checks"]["independent_holdout"]["status"] == "failed"
