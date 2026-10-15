import pytest
from app.contracts.ai_report import AIReportResponse
from app.domain.audit import AuditError
from app.services.report_generation import (
    report_source,
    source_fingerprint,
    validate_response,
)


def source():
    return {
        "audit": {
            "id": "task",
            "project_name": "任意项目",
            "snapshot_hash": "snapshot",
            "language": "python",
            "status": "completed",
            "findings": [],
            "coverage": {},
        },
        "summary": {"static_alerts": 0},
        "candidates": [
            {
                "id": "one",
                "title": "English title",
                "description": "Source-specific details",
                "status": "pending",
                "evidence_ids": ["source"],
                "location": {"file": "other.py", "line": 10},
            }
        ],
        "evidence": [
            {
                "id": "source",
                "kind": "code",
                "reference": {"file": "other.py", "start_line": 10},
                "content": "return user_input",
                "snapshot_hash": "snapshot",
                "digest": "digest",
            }
        ],
        "decisions": [],
        "repairs": [],
        "rules": [],
        "coverage": {},
        "stages": [],
    }


def response():
    return AIReportResponse.model_validate(
        {
            "overview": "本项目存在一项待确认的安全候选，需要核对输入的实际来源。",
            "issues": [
                {
                    "candidate_id": "one",
                    "title": "输出处理需要复核",
                    "explanation": "该函数返回输入，是否存在风险取决于响应类型和已有防护。",
                    "impact": "若不可信内容作为网页代码处理，可能影响访问者。",
                    "fix_suggestions": ["核实响应类型，按输出上下文处理不可信输入。"],
                    "verification_suggestions": ["比较正常输入与攻击输入的实际响应。"],
                    "evidence_ids": ["source"],
                }
            ],
            "repair_review": "尚无修复记录，不能声称修复已通过。",
            "limitations": ["没有执行运行时攻击验证。"],
            "next_steps": ["核对源码并记录人工判断。"],
        }
    )


def test_report_sources_are_project_specific_and_never_include_credentials_or_prompt_history():
    data = source()
    data["stages"] = [
        {
            "kind": "report",
            "model_config_snapshot": {"api_key": "secret"},
            "result": {"old_report": "old"},
        }
    ]
    assert "secret" not in str(report_source(data))
    assert source_fingerprint(data) == source_fingerprint(source())
    changed = source()
    changed["candidates"][0]["status"] = "confirmed"
    assert source_fingerprint(changed) != source_fingerprint(data)


def test_unknown_or_cross_candidate_evidence_is_rejected():
    result = response()
    result.issues[0].evidence_ids = ["invented"]
    with pytest.raises(AuditError):
        validate_response(result, report_source(source()))


def test_model_cannot_silently_omit_candidates_or_add_new_verdicts():
    result = response()
    result.issues = []
    with pytest.raises(AuditError):
        validate_response(result, report_source(source()))
    with pytest.raises(ValueError):
        AIReportResponse.model_validate({**response().model_dump(), "confirmed": True})


def test_chinese_narrative_is_required_and_valid_response_does_not_modify_judgment():
    data = report_source(source())
    validate_response(response(), data)
    assert data["candidates"][0]["status"] == "pending"
    with pytest.raises(ValueError):
        AIReportResponse.model_validate(
            {**response().model_dump(), "overview": "English-only report"}
        )


def test_report_redacts_embedded_credentials_and_preserves_saved_uncertainty():
    data = source()
    data["repairs"] = [
        {
            "validation": {
                "tests": {"output": "Authorization: Bearer synthetic-private-value"}
            }
        }
    ]
    assessment = {
        "candidate_id": "one",
        "reason": "response type unknown",
        "missing_premises": ["HTML response"],
        "runtime_unknowns": ["deployment"],
        "counterevidence_ids": [],
    }
    data["stages"] = [
        {"kind": "review", "result": {"batches": [{"assessments": [assessment]}]}}
    ]
    projected = report_source(data)
    assert "synthetic-private-value" not in str(projected)
    assert "HTML response" in str(projected)
    before = source_fingerprint(data)
    assessment["missing_premises"] = ["different uncertainty"]
    assert before != source_fingerprint(data)


def test_reports_batch_large_candidate_sets_without_omitting_any_ids():
    from app.services.report_materials import report_batches

    data = report_source(source())
    data["candidates"] = [
        {**data["candidates"][0], "id": str(index)} for index in range(41)
    ]
    batches = report_batches(data)
    assert len(batches) > 1
    assert [row["id"] for batch in batches for row in batch["candidates"]] == [
        str(i) for i in range(41)
    ]
    assert all(len(batch["candidates"]) <= 4 for batch in batches)


def test_source_literals_and_connection_credentials_are_redacted():
    from app.services.report_materials import redact

    value = "api_key='synthetic-value' sk-syntheticcredential123 https://user:synthetic-password@host/"
    result = redact(value)
    assert "synthetic" not in result
    assert "[凭据已隐藏]" in result


def test_batched_generation_includes_every_candidate_in_final_ai_narrative(tmp_path):
    import hashlib
    import json
    from types import SimpleNamespace

    from app.services.report_generation import ReportService

    data = report_source(source())
    data["candidates"] = [
        {**data["candidates"][0], "id": str(index)} for index in range(41)
    ]
    (tmp_path / "report-source.json").write_text(json.dumps(data), encoding="utf-8")
    calls = []

    class Provider:
        def generate(self, purpose, payload, schema):
            calls.append(payload)
            narrative = response().model_dump()
            narrative["overview"] = (
                "独立的全项目审计结论，不重复分批说明。"
                if payload["batch"]["scope"] == "global"
                else "仅对当前批次的漏洞进行说明。"
            )
            narrative["issues"] = [
                {**narrative["issues"][0], "candidate_id": row["id"]}
                for row in payload["candidates"]
            ]
            return schema.model_validate(narrative)

    service = ReportService.__new__(ReportService)
    service.stage_id, service.directory, service.provider = (
        "test-only",
        tmp_path,
        Provider(),
    )
    service.repository = SimpleNamespace(
        active=lambda *a: None, update=lambda *a, **kw: None
    )
    fingerprint = hashlib.sha256(
        json.dumps(data, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()
    result = service.generate(
        {"source_fingerprint": fingerprint, "material_fingerprint": fingerprint}
    )
    assert len(calls) == 12
    assert result["narrative"]["overview"] == "独立的全项目审计结论，不重复分批说明。"
    assert [issue["candidate_id"] for issue in result["narrative"]["issues"]] == [
        str(i) for i in range(41)
    ]


def test_flask_config_literals_are_redacted_and_current_judgments_are_retained():
    from app.services.report_materials import redact, report_batches
    from app.services.report_overview import overview_material

    for text in [
        "app.secret_key = 'SYNTHETIC_FLASK_SECRET'",
        "app.config['SECRET_KEY'] = 'SYNTHETIC_FLASK_SECRET'",
        "refresh_token='SYNTHETIC_FLASK_SECRET'",
        '"password": "SYNTHETIC_FLASK_SECRET"',
    ]:
        assert "SYNTHETIC_FLASK_SECRET" not in redact(text)
    data = report_source(source())
    data["candidates"].append({**data["candidates"][0], "id": "two"})
    data["decisions"] = [
        {"candidate_id": "two", "reason": "Unique current decision"}
    ] + [{"candidate_id": "one", "reason": str(i)} for i in range(40)]
    data["coverage"] = {
        "dual_engine": {
            "codeql": {"status": "failed"},
            "scout": {"status": "completed", "uninspected_windows": 4},
        }
    }
    batch = report_batches(data)[0]
    overview = overview_material(data)
    assert {row["candidate_id"] for row in batch["decisions"]} == {"one", "two"}
    assert overview["coverage"]["dual_engine"]["codeql"]["status"] == "failed"
    assert overview["coverage"]["dual_engine"]["scout"]["uninspected_windows"] == 4


def test_private_fingerprint_detects_secret_changes_without_sending_them():
    data = source()
    data["repairs"] = [{"changes": [{"new_text": "password='SYNTHETIC_OLD'"}]}]
    before = source_fingerprint(data)
    data["repairs"][0]["changes"][0]["new_text"] = "password='SYNTHETIC_NEW'"
    assert source_fingerprint(data) != before
    assert "SYNTHETIC_NEW" not in str(report_source(data))


def test_repair_history_does_not_multiply_issue_batches_or_hide_failed_checks():
    from copy import deepcopy

    from app.services.report_materials import report_batches
    from app.services.report_overview import overview_material

    data = report_source(source())
    data["candidates"] = [{**data["candidates"][0], "id": str(i)} for i in range(17)]
    expected = report_batches(data)
    data["repairs"] = [
        {
            "id": str(i),
            "status": "needs_review",
            "candidate_ids": ["0"],
            "changes": [
                {
                    "file": "app.py",
                    "old_text": "old line" * 10000,
                    "new_text": "new line" * 10000,
                    "reason": "需要修复输出编码",
                }
            ],
            "validation": {
                "application": {"status": "failed", "output": "旧文本匹配失败"}
            },
        }
        for i in range(3)
    ]
    data["verification"] = [{"repair_id": "0", "comparison": {"status": "missing"}}]
    before = deepcopy(data)
    assert report_batches(data) == expected
    overview = overview_material(data)
    assert len(overview["review_summary"]) == 17
    assert overview["required_candidate_ids"] == []
    assert len(overview["repairs"]) == 3
    assert all(
        row["validation"]["application"]["status"] == "failed"
        for row in overview["repairs"]
    )
    assert overview["verification"][0]["comparison"]["status"] == "missing"
    assert all("new_text" not in row["changes"][0] for row in overview["repairs"])
    assert data == before


def test_review_details_and_uncertainty_reach_report_batches_and_freshness():
    from app.services.report_materials import report_batches

    data = source()
    detail = {
        "title": "本项目的输出风险",
        "description": "函数将输入直接返回",
        "impact": "响应类型仍待核实",
        "exploitation": {
            "example": "synthetic request",
            "execution_status": "not_executed",
        },
        "evidence_ids": ["source"],
    }
    data["candidates"][0]["review"] = {"status": "insufficient", "detail": detail}
    data["candidates"][0]["classification"] = {"status": "insufficient", "source": "ai"}
    assessment = {
        "candidate_id": "one",
        "assessment": "insufficient",
        "detail": detail,
        "missing_premises": ["响应类型"],
        "runtime_unknowns": ["部署环境"],
    }
    data["stages"] = [
        {
            "id": "review-stage",
            "kind": "review",
            "status": "completed",
            "result": {
                "batches": [{"assessments": [assessment]}],
                "unreviewed_candidate_ids": ["unchecked"],
                "root_relations": [
                    {"candidate_ids": ["one", "unchecked"], "relationship": "possible"}
                ],
            },
        }
    ]
    batch = report_batches(report_source(data))[0]
    assert batch["candidates"][0]["classification"]["status"] == "insufficient"
    assert (
        batch["assessments"][0]["detail"]["exploitation"]["execution_status"]
        == "not_executed"
    )
    assert batch["assessments"][0]["runtime_unknowns"] == ["部署环境"]
    assert batch["review_context"][0]["unreviewed_candidate_ids"] == ["unchecked"]
    assert batch["review_context"][0]["root_relations"][0]["relationship"] == "possible"
    before = source_fingerprint(data)
    detail["exploitation"]["example"] = "changed synthetic request"
    assert source_fingerprint(data) != before


def test_report_batches_do_not_duplicate_review_narratives_or_omit_current_evidence():
    from copy import deepcopy

    from app.services.report_materials import report_batches

    data = report_source(source())
    detail = {
        "description": "中文复审说明，输入输出均需核实。" * 120,
        "exploitation": {
            "example": "仅演示，未执行",
            "execution_status": "not_executed",
        },
    }
    data["candidates"] = [
        {
            **deepcopy(data["candidates"][0]),
            "id": str(i),
            "review": {
                "stage_id": "current",
                "status": "insufficient",
                "detail": detail,
            },
            "classification": {"status": "insufficient", "source": "human"},
        }
        for i in range(17)
    ]
    data["assessments"] = [
        {
            "candidate_id": str(i),
            "detail": detail,
            "missing_premises": ["真实响应类型尚未知"],
        }
        for i in range(17)
    ]
    data["review_context"] = [
        {
            "stage_id": "old",
            "root_relations": [
                {"candidate_ids": ["old-id"], "reason": "历史记录" * 500}
            ],
        },
        {"stage_id": "current", "unreviewed_candidate_ids": [], "root_relations": []},
    ]
    data["evidence"][0]["content"] = "完整源码仍保留在冻结材料和导出报告。" * 300
    before = deepcopy(data)
    batches = report_batches(data)
    assert [row["id"] for batch in batches for row in batch["candidates"]] == [
        str(i) for i in range(17)
    ]
    assert len(batches) == 5
    for batch in batches:
        assert batch["required_candidate_ids"] == [
            row["id"] for row in batch["candidates"]
        ]
        assert all("detail" not in row["review"] for row in batch["candidates"])
        assert all(
            row["detail"]["exploitation"]["execution_status"] == "not_executed"
            for row in batch["assessments"]
        )
        assert all(
            row["missing_premises"] == ["真实响应类型尚未知"]
            for row in batch["assessments"]
        )
        assert all(
            ids == ["source"] for ids in batch["issue_evidence_binding"].values()
        )
        assert {row["id"] for row in batch["evidence"]} == {"source"}
        assert "材料已节选" in batch["evidence"][0]["content"]
        assert len(batch["evidence"][0]["content"]) < 700
        assert all(row["stage_id"] == "current" for row in batch["review_context"])
    assert data == before
    before = source_fingerprint(data)
    data["candidates"][0]["classification"] = {"status": "excluded", "source": "human"}
    assert source_fingerprint(data) != before
