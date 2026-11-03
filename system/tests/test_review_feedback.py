"""Source cache, proof preservation, budgets and cancellation for accepted uncertainty."""

import pytest
from app.adapters.review_evidence import retained_pages
from app.core.db import engine
from app.domain.audit import AuditError
from app.persistence.stage_models import Evidence, StageRun
from app.persistence.stage_repository import StageCancelled
from app.services.evidence import EvidenceService
from app.workflows.review import build_review_graph
from sqlmodel import Session

from tests.review_feedback_fixtures import FILES, FeedbackModel, make_service


def run(service):
    build_review_graph(service).invoke({"stage_id": service.stage_id})
    return service.repository.get(service.stage_id).result


@pytest.mark.parametrize("pipeline_context", [FILES], indirect=True)
def test_existing_stage_evidence_is_reused_and_initial_uncertainty_is_preserved(
    pipeline_context,
):
    provider = FeedbackModel()
    service = make_service(pipeline_context, provider, seed=True)
    result = run(service)
    assert provider.usage["calls"] == 2
    assert not any(
        p["reference"].get("file") == "controls.py"
        for p in provider.seen[0]["evidence"]
    )
    assert service.seeded_page["id"] in [p["id"] for p in provider.seen[1]["evidence"]]
    assert result["recommendations"][0]["recommendation"] == "supported"
    batch = result["batches"][0]
    assert (
        batch["assessment_history"][0]["assessments"][0]["assessment"] == "insufficient"
    )
    assert batch["assessment_history"][0]["call_reference"].endswith("call-0")
    assert batch["call_reference"].endswith("call-1")
    attempt = result["review_feedback_attempts"][0]
    assert attempt["status"] == "reassessed"
    assert attempt["source_events"][0]["origin"] == "retained_stage_evidence"


@pytest.mark.parametrize("pipeline_context", [FILES], indirect=True)
def test_uncached_missing_source_is_read_and_supported_sibling_is_not_reassessed(
    pipeline_context,
):
    provider = FeedbackModel()
    service = make_service(pipeline_context, provider, siblings=True)
    result = run(service)
    assert len(result["recommendations"]) == 2
    assert len({r["id"] for r in result["recommendations"]}) == 2
    assert (
        len(provider.seen[0]["targets"]) == 2 and len(provider.seen[1]["targets"]) == 1
    )
    assert (
        result["review_feedback_attempts"][0]["source_events"][0]["origin"]
        == "targeted_source_read"
    )
    assert all(r["recommendation"] == "supported" for r in result["recommendations"])


@pytest.mark.parametrize(
    "pipeline_context",
    [{**FILES, "controls.py": "def accept(value):\n    return '1'\n"}],
    indirect=True,
)
def test_real_counterevidence_can_exclude_instead_of_forcing_a_true_positive(
    pipeline_context,
):
    result = run(make_service(pipeline_context, FeedbackModel("excluded")))
    assessment = result["batches"][0]["assessments"][0]
    assert assessment["assessment"] == "excluded" and assessment["counterevidence_ids"]
    assert assessment["premises"][-1]["status"] == "contradicted"


@pytest.mark.parametrize("pipeline_context", [FILES], indirect=True)
@pytest.mark.parametrize(
    "mode",
    ["still_missing", "invalid_revision", "provider_failure", "pending_revision"],
)
def test_unresolved_rejected_or_interrupted_feedback_preserves_valid_uncertainty(
    pipeline_context, mode
):
    provider = FeedbackModel(mode)
    service = make_service(pipeline_context, provider)
    result = run(service)
    assert provider.usage["calls"] == 2
    assert result["recommendations"][0]["recommendation"] == "insufficient"
    assert not result["unreviewed_candidate_ids"]
    assert len(result["review_feedback_attempts"]) == 1
    attempt = result["review_feedback_attempts"][0]
    assert (
        attempt["status"]
        == {
            "still_missing": "reassessed",
            "invalid_revision": "rejected",
            "provider_failure": "incomplete",
            "pending_revision": "rejected",
        }[mode]
    )
    if mode == "provider_failure":
        assert result["stop_reason"] == "provider_error"
    run(service)
    assert provider.usage["calls"] == 2, "resume must not renew the allowance"


@pytest.mark.parametrize("pipeline_context", [FILES], indirect=True)
def test_feedback_cannot_expand_original_call_budget(pipeline_context):
    provider = FeedbackModel(max_calls=1)
    result = run(make_service(pipeline_context, provider))
    assert provider.usage["calls"] == 1
    assert result["recommendations"][0]["recommendation"] == "insufficient"
    assert not result.get("review_feedback_attempts")


@pytest.mark.parametrize("pipeline_context", [FILES], indirect=True)
def test_explicit_ablation_disables_only_insufficient_supplementation(pipeline_context):
    provider = FeedbackModel()
    result = run(
        make_service(pipeline_context, provider, supplement_insufficient=False)
    )
    assert not result["review_feedback_policy"]["enabled"]
    assert result["recommendations"][0]["recommendation"] == "insufficient"
    assert provider.usage["calls"] == 1


@pytest.mark.parametrize(
    "pipeline_context",
    [
        {
            **FILES,
            "controls.py": "def accept(value):\n    return value\n# " + "x" * 11000,
        }
    ],
    indirect=True,
)
def test_context_overflow_records_gap_without_truncating_source_or_losing_initial_verdict(
    pipeline_context,
):
    provider = FeedbackModel()
    result = run(make_service(pipeline_context, provider, max_context_chars=14000))
    assert provider.usage["calls"] == 1
    assert result["recommendations"][0]["recommendation"] == "insufficient"
    events = result["review_feedback_attempts"][0]["source_events"]
    assert any(e["status"] == "context_budget" for e in events)


@pytest.mark.parametrize("pipeline_context", [FILES], indirect=True)
def test_cache_from_another_stage_is_never_reused(pipeline_context):
    service = make_service(pipeline_context, FeedbackModel())
    with Session(engine) as db:
        other = StageRun(audit_id=service.stage.audit_id, kind="review")
        db.add(other)
        db.commit()
        db.refresh(other)
        other_id = str(other.id)
    foreign = EvidenceService(str(service.stage.audit_id), other_id, []).read(
        "controls.py", 1, 151
    )
    assert retained_pages(service.evidence, "controls.py") == []
    result = run(service)
    ids = result["batches"][0]["assessments"][0]["evidence_ids"]
    assert foreign["id"] not in ids
    assert (
        result["review_feedback_attempts"][0]["source_events"][0]["origin"]
        == "targeted_source_read"
    )


@pytest.mark.parametrize("pipeline_context", [FILES], indirect=True)
def test_corrupt_retained_evidence_is_an_integrity_failure(pipeline_context):
    service = make_service(pipeline_context, FeedbackModel(), seed=True)
    with Session(engine) as db:
        from uuid import UUID

        page = db.get(Evidence, UUID(service.seeded_page["id"]))
        page.content = "forged source"
        db.add(page)
        db.commit()
    with pytest.raises(AuditError, match="补证缓存") as error:
        run(service)
    assert error.value.code == "integrity_error"


@pytest.mark.parametrize("pipeline_context", [FILES], indirect=True)
def test_cancellation_during_supplementation_is_not_converted_to_insufficient(
    pipeline_context, monkeypatch
):
    service = make_service(pipeline_context, FeedbackModel())

    def cancelled(*_args):
        raise StageCancelled("synthetic cancellation")

    monkeypatch.setattr("app.services.review_feedback.source_pages", cancelled)
    with pytest.raises(StageCancelled):
        run(service)


@pytest.mark.parametrize("pipeline_context", [FILES], indirect=True)
def test_prepared_legacy_stage_does_not_silently_enable_feedback(pipeline_context):
    from app.services.context_materials import save_json
    from app.services.review_pool import pool_for_resume
    from app.services.unified_review import UnifiedReview

    provider = FeedbackModel()
    service = make_service(pipeline_context, provider)
    reviewer = UnifiedReview(service)
    pool = pool_for_resume(reviewer)
    pool["inputs"].pop("supplement_insufficient")
    current = service.repository.get(service.stage_id).result
    service.repository.update(service.stage_id, result={**current, "pool": pool})
    save_json(reviewer.directory / "review-pool.json", pool)
    result = run(service)
    assert not result["review_feedback_policy"]["enabled"]
    assert provider.usage["calls"] == 1


@pytest.mark.parametrize(
    "pipeline_context", [{**FILES, "controls.py": ""}], indirect=True
)
def test_empty_source_is_not_claimed_as_supplied_evidence(pipeline_context):
    provider = FeedbackModel()
    result = run(make_service(pipeline_context, provider))
    assert provider.usage["calls"] == 1
    assert result["review_feedback_attempts"][0]["status"] == "no_source_progress"
    assert (
        result["review_feedback_attempts"][0]["source_events"][0]["status"]
        == "no_source_pages"
    )


@pytest.mark.parametrize("pipeline_context", [FILES], indirect=True)
def test_latest_review_contract_preserves_narrative_and_source_ids_after_feedback(
    pipeline_context,
):
    from app.contracts.discovery_semantics import UnifiedReviewResponseV8

    class Presented(FeedbackModel):
        def generate(self, purpose, payload, schema):
            data = (
                super()
                .generate(purpose, payload, UnifiedReviewResponseV8)
                .model_dump(mode="json")
            )
            for a in data["candidate_assessments"]:
                a["detail"] = {
                    "title": "本项目输入与求值操作复审",
                    "description": "实际读取项目代码与关联控制后判断输入是否仍可影响求值操作。",
                    "impact": "若输入未经有效限制，可能使求值操作处理攻击者控制的内容。",
                    "evidence_ids": a["evidence_ids"],
                    "exploitation": {
                        "status": "missing_preconditions",
                        "expected_result": "本测试仅验证源码复审流程，未执行任何利用或目标程序。",
                    },
                }
            return schema.model_validate(data)

    model = Presented()
    result = run(make_service(pipeline_context, model, version="12"))
    assessment = result["batches"][0]["assessments"][0]
    assert model.usage["calls"] == 2
    assert assessment["assessment"] == "supported"
    assert assessment["detail"]["exploitation"]["execution_status"] == "not_executed"
    assert result["batches"][0]["assessment_history"][0]["assessments"][0]["detail"]


@pytest.mark.parametrize("pipeline_context", [FILES], indirect=True)
def test_all_three_uncertain_targets_receive_one_bounded_revision(pipeline_context):
    provider = FeedbackModel(max_calls=4)
    service = make_service(pipeline_context, provider, seed=True, copies=3)
    result = run(service)
    assert provider.usage["calls"] == 4
    assert [len(p["targets"]) for p in provider.seen] == [3, 1, 1, 1]
    assert len(result["recommendations"]) == 3
    assert len(result["review_feedback_attempts"]) == 3
    assert len(result["batches"][0]["assessment_history"]) == 3
    assert all(a["status"] == "reassessed" for a in result["review_feedback_attempts"])


@pytest.mark.parametrize("pipeline_context", [FILES], indirect=True)
def test_reused_page_does_not_force_final_before_a_new_fact_can_be_read(
    pipeline_context,
):
    class ReadThenFollow(FeedbackModel):
        def generate(self, purpose, payload, schema):
            if len(self.seen) < 2:
                from copy import deepcopy

                if self.seen:
                    assert payload["latest_tool_observation"]["reused"]
                    assert not payload["finalize_required"]
                file = "app.py" if not self.seen else "controls.py"
                self.seen.append(deepcopy(payload))
                self.usage["calls"] += 1
                return schema.model_validate(
                    {
                        "action": "tool",
                        "tool": {
                            "name": "read_source",
                            "arguments": {"file": file, "start_line": 1, "end_line": 3},
                        },
                    }
                )
            return super().generate(purpose, payload, schema)

    model = ReadThenFollow(max_calls=3)
    result = run(make_service(pipeline_context, model))
    assert model.usage["calls"] == 3
    assert result["recommendations"][0]["recommendation"] == "supported"


@pytest.mark.parametrize("pipeline_context", [FILES], indirect=True)
@pytest.mark.parametrize(
    "missing",
    [
        "尚缺真实业务授权要求，不能从公开操作推导。",
        "需读取 ../outside.py 才能验证保护。",
    ],
)
def test_unlocated_policy_or_out_of_scope_source_stays_uncertain(
    pipeline_context, missing
):
    class Unresolvable(FeedbackModel):
        def generate(self, purpose, payload, schema):
            data = super().generate(purpose, payload, schema).model_dump(mode="json")
            data["candidate_assessments"][0]["missing_premises"] = [missing]
            data["candidate_assessments"][0]["premises"][-1]["reason"] = missing
            return schema.model_validate(data)

    model = Unresolvable()
    result = run(make_service(pipeline_context, model))
    assert model.usage["calls"] == 1
    assert result["recommendations"][0]["recommendation"] == "insufficient"
    assert result["review_feedback_attempts"][0]["status"] in {
        "no_local_source_target",
        "no_source_progress",
    }


@pytest.mark.parametrize("pipeline_context", [FILES], indirect=True)
def test_feedback_cannot_create_unrequested_findings_even_when_discovery_is_enabled(
    pipeline_context,
):
    from app.persistence.stage_models import Candidate
    from sqlmodel import select

    class ExtraFinding(FeedbackModel):
        def generate(self, purpose, payload, schema):
            data = super().generate(purpose, payload, schema).model_dump(mode="json")
            if payload.get("feedback_revision"):
                a = data["candidate_assessments"][0]
                data["new_findings"] = [
                    {
                        "title": "额外发现",
                        "description": "这条源代码定位有效，但补证不应扩大候选范围。",
                        "weakness": "CWE-94",
                        "primary_location": {"file": "app.py", "line": 2},
                        "related_target": a["candidate_id"],
                        "evidence_ids": a["evidence_ids"],
                    }
                ]
            return schema.model_validate(data)

    service = make_service(pipeline_context, ExtraFinding(), discover=True)
    result = run(service)
    assert len(result["recommendations"]) == 1
    assert result["batches"][0]["rejected_new_findings"]
    with Session(engine) as db:
        assert (
            len(
                db.exec(
                    select(Candidate).where(Candidate.stage_id == service.stage.id)
                ).all()
            )
            == 1
        )
