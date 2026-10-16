from app.services.reports import markdown_report


def report_data():
    return {
        "audit": {
            "project_name": "XSS 示例",
            "snapshot_hash": "snapshot",
            "language": "python",
            "codeql_version": "2.23.5",
            "status": "completed",
            "findings": [],
        },
        "summary": {
            "static_alerts": 0,
            "candidate_states": {
                "confirmed": 1,
                "pending": 0,
                "excluded": 0,
                "insufficient": 0,
            },
        },
        "coverage": {},
        "discovery": [],
        "root_relations": [],
        "stages": [],
        "anchor_assessments": [],
        "candidates": [
            {
                "id": "one",
                "title": "Reflected XSS",
                "description": "Unescaped request input",
                "weakness": "CWE-79",
                "status": "confirmed",
                "location": {"file": "app.py", "line": 7},
                "evidence_ids": ["source"],
            }
        ],
        "evidence": [
            {
                "id": "source",
                "kind": "code",
                "reference": {"file": "app.py", "start_line": 7},
                "content": "    return request.args['payload']",
            }
        ],
        "decisions": [],
        "repairs": [
            {
                "id": "repair",
                "status": "needs_review",
                "changes": [],
                "validation": {
                    "environment": {"status": "blocked", "output": "验证镜像未安装"},
                    "semantic_scope": {"status": "documented"},
                },
            }
        ],
        "rules": [],
        "limitations": ["未报告告警不代表安全"],
    }


def test_markdown_starts_with_plain_language_and_evidence_location():
    text = markdown_report(report_data())
    before_json = text.split("```json")[0]
    assert "已确认 1" in before_json
    assert "app.py:7" in before_json
    assert "浏览器" in before_json
    assert "环境未就绪" in before_json
    assert "功能" in before_json
    assert "原始记录" in text


def test_unknown_candidates_are_not_presented_as_confirmed_vulnerabilities():
    data = report_data()
    data["summary"]["candidate_states"] = {"confirmed": 0, "pending": 1}
    data["candidates"][0].update(status="pending", weakness="unknown", location={})
    text = markdown_report(data).split("原始记录")[0]
    assert "待确认 1 个" in text
    assert "已确认 0 个" in text
    assert "位置待核实" in text
    assert "已证实" not in text


def test_syntax_pass_does_not_claim_business_or_security_success():
    data = report_data()
    data["repairs"][0]["validation"] = {
        "isolated_tests": {"status": "passed", "profile": "syntax"},
        "rescan": {"status": "not_run"},
    }
    text = markdown_report(data).split("原始记录")[0]
    assert "语法检查通过" in text
    assert "漏洞验证：未执行" in text
    assert "功能测试：未执行" in text
    assert "漏洞验证：通过" not in text
