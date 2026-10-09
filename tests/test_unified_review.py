"""Unified review evidence gates, partial batches and preserved human boundaries."""

from uuid import uuid4

import pytest
from app.contracts.unified_review import UnifiedReviewResponse
from app.core.db import engine
from app.persistence.audit_models import AuditRun
from app.persistence.stage_models import Candidate, StageRun
from app.persistence.stage_repository import StageRepository
from app.services.review import ReviewService
from app.workflows.review import build_review_graph
from sqlmodel import Session, select

from tests.test_dual_discovery import HypothesisModel, run_scout


class ReviewModel(HypothesisModel):
    def generate(self, purpose, payload, schema):
        assert purpose == "review"
        self.usage["calls"] += 1
        self.seen.append(payload)
        ids = [r["id"] for r in payload["evidence"] if r["kind"] == "code"]
        return schema.model_validate(
            {
                "action": "final",
                "summary": "Source-backed recommendations require human confirmation.",
                "candidate_assessments": [
                    {
                        "candidate_id": r["candidate_id"],
                        "assessment": "supported",
                        "weakness": "CWE-094",
                        "reason": "The supplied code shows an unsafe input-to-operation path.",
                        "checked_premises": [
                            "Source and primary operation were inspected."
                        ],
                        "evidence_ids": ids,
                    }
                    for r in payload["targets"]
                ],
                "root_relations": [
                    {
                        "candidate_ids": [
                            r["candidate_id"] for r in payload["targets"]
                        ],
                        "relationship": "related",
                        "reason": "These hypotheses share source but their actual root identity is unresolved.",
                        "evidence_ids": ids,
                    }
                ]
                if len(payload["targets"]) > 1
                else [],
            }
        )


def run_review(ctx, provider=None, version="4", **inputs):
    with Session(engine) as db:
        stage = StageRun(
            audit_id=ctx["run_id"], kind="review", prompt_version=version, inputs=inputs
        )
        db.add(stage)
        db.commit()
        db.refresh(stage)
        identifier = str(stage.id)
    StageRepository().claim(identifier)
    service = ReviewService(identifier, provider or ReviewModel())
    build_review_graph(service).invoke({"stage_id": identifier})
    return service


def test_both_sources_reviewed_without_deleting_hypotheses(pipeline_context):
    ctx = pipeline_context
    scout = run_scout(ctx)
    service = run_review(ctx)
    result = service.repository.get(service.stage_id).result
    assert {r["origin"] for r in result["pool"]["entries"]} == {"static", "scout"}
    assert len(result["recommendations"]) == 2 and result["root_relations"]
    with Session(engine) as db:
        original = db.exec(
            select(Candidate).where(Candidate.stage_id == scout.stage.id)
        ).one()
        rows = db.exec(
            select(Candidate).where(Candidate.audit_id == ctx["run_id"])
        ).all()
    assert original.model_assessment == "pending" and original.status == "pending"
    assert len(rows) == 3 and all(r.status == "pending" for r in rows)
    report = ctx["client"].get(f"/api/v1/audits/{ctx['run_id']}/report").json()
    assert report["summary"]["candidate_states"]["confirmed"] == 0
    assert (
        len(report["candidates"]) == 3
        and report["discovery"]
        and report["root_relations"]
    )


def test_no_static_alerts_and_no_keyword_anchor_can_be_reviewed(pipeline_context):
    ctx = pipeline_context
    with Session(engine) as db:
        run = db.get(AuditRun, ctx["run_id"])
        run.findings = []
        db.add(run)
        db.commit()
    run_scout(ctx)
    service = run_review(ctx)
    result = service.repository.get(service.stage_id).result
    assert len(result["recommendations"]) == 1
    assert result["pool"]["entries"][0]["origin"] == "scout"
    context = service.provider.seen[0]
    assert "app.py" in context["source_inventory"]["files"]
    assert context["source_inventory"]["omitted_files"] == 0
    assert "Deployed exploitability" in context["assessment_boundary"]


def test_exclusion_requires_counterevidence_and_no_missing_premise():
    assessment = {
        "candidate_id": str(uuid4()),
        "assessment": "excluded",
        "reason": "Protection is only a model assumption.",
        "checked_premises": ["Checked local function"],
        "evidence_ids": [str(uuid4())],
    }
    with pytest.raises(ValueError, match="counterevidence"):
        UnifiedReviewResponse.model_validate(
            {"action": "final", "candidate_assessments": [assessment]}
        )
    assessment["counterevidence_ids"] = assessment["evidence_ids"]
    assessment["missing_premises"] = ["Upstream guard remains unknown"]
    with pytest.raises(ValueError, match="Unresolved"):
        UnifiedReviewResponse.model_validate(
            {"action": "final", "candidate_assessments": [assessment]}
        )


def test_unprovided_counterevidence_leaves_candidate_unreviewed(pipeline_context):
    class Invented(ReviewModel):
        def generate(self, purpose, payload, schema):
            response = super().generate(purpose, payload, schema)
            response.candidate_assessments[0].assessment = "excluded"
            response.candidate_assessments[0].counterevidence_ids = [uuid4()]
            return response

    service = run_review(pipeline_context, Invented())
    result = service.repository.get(service.stage_id).result
    assert (
        result["coverage_status"] == "partial"
        and len(result["unreviewed_candidate_ids"]) == 1
    )
    assert result["batches"][0]["status"] == "incomplete"
    assert not result["recommendations"]


def test_omission_is_unreviewed_not_excluded(pipeline_context):
    class Omitted(ReviewModel):
        def generate(self, _purpose, _payload, schema):
            return schema.model_validate(
                {
                    "action": "final",
                    "summary": "The necessary source context is not resolved.",
                }
            )

    service = run_review(pipeline_context, Omitted())
    assert (
        len(service.repository.get(service.stage_id).result["unreviewed_candidate_ids"])
        == 1
    )


@pytest.mark.parametrize(
    "pipeline_context",
    [{"app.py": "value = eval(input())\n", "other.py": "value = eval(input())\n"}],
    indirect=True,
)
def test_batched_budget_retains_unprocessed_candidates(pipeline_context):
    run_scout(pipeline_context)
    provider = ReviewModel()
    service = run_review(pipeline_context, provider, batch_size=1, max_batches=1)
    result = service.repository.get(service.stage_id).result
    assert len(result["pool"]["entries"]) == 3
    assert len(result["unreviewed_candidate_ids"]) == 2 and provider.usage["calls"] == 1
    build_review_graph(service).invoke({"stage_id": service.stage_id})
    assert provider.usage["calls"] == 1


def test_tool_trace_does_not_destroy_committed_pool(pipeline_context):
    class ReadGuard(ReviewModel):
        def generate(self, purpose, payload, schema):
            if not payload["tool_trace"]:
                return schema.model_validate(
                    {
                        "action": "tool",
                        "tool": {
                            "name": "read_source",
                            "arguments": {
                                "file": "app.py",
                                "start_line": 1,
                                "end_line": 1,
                            },
                        },
                    }
                )
            return super().generate(purpose, payload, schema)

    service = run_review(pipeline_context, ReadGuard())
    result = service.repository.get(service.stage_id).result
    assert result["pool"]["entries"] and result["batches"][0]["trace"]
    assert len(result["recommendations"]) == 1


def test_cross_audit_scout_input_is_rejected(pipeline_context):
    with pytest.raises(Exception, match="不属于"):
        run_review(pipeline_context, scout_candidate_ids=[str(uuid4())])


def test_repeat_read_receives_reused_evidence_and_eof(pipeline_context):
    class Repeat(ReviewModel):
        def generate(self, purpose, payload, schema):
            if not payload.get("latest_tool_observation"):
                return schema.model_validate(
                    {
                        "action": "tool",
                        "tool": {
                            "name": "read_source",
                            "arguments": {
                                "file": "app.py",
                                "start_line": 1,
                                "end_line": 1,
                            },
                        },
                    }
                )
            assert payload["latest_tool_observation"]["reused"]
            assert payload["source_windows"][0]["complete_file"]
            return super().generate(purpose, payload, schema)

    service = run_review(pipeline_context, Repeat())
    assert len(service.repository.get(service.stage_id).result["recommendations"]) == 1


def test_stalled_repeat_reads_remain_unknown(pipeline_context):
    class Stalled(ReviewModel):
        def generate(self, _purpose, _payload, schema):
            return schema.model_validate(
                {
                    "action": "tool",
                    "tool": {
                        "name": "read_source",
                        "arguments": {"file": "app.py", "start_line": 1, "end_line": 1},
                    },
                }
            )

    service = run_review(pipeline_context, Stalled())
    result = service.repository.get(service.stage_id).result
    assert (
        result["batches"][0]["code"] == "no_progress"
        and result["unreviewed_candidate_ids"]
    )


def test_repeated_identical_scout_hypotheses_reuse_logical_identity(pipeline_context):
    run_scout(pipeline_context)
    run_scout(pipeline_context)
    with Session(engine) as db:
        rows = db.exec(
            select(Candidate).where(Candidate.audit_id == pipeline_context["run_id"])
        ).all()
    assert len(rows) == 2 and len({r.identity_key for r in rows}) == 1
    service = run_review(pipeline_context)
    assert (
        len(
            [
                r
                for r in service.repository.get(service.stage_id).result["pool"][
                    "entries"
                ]
                if r["origin"] == "scout"
            ]
        )
        == 1
    )


def test_invalid_optional_root_relation_preserves_valid_assessments(pipeline_context):
    class UngroundedRelation(ReviewModel):
        def generate(self, purpose, payload, schema):
            valid = super().generate(purpose, payload, schema).model_dump(mode="json")
            # Correct-looking root proposal cites a real document, but no target source.
            doc = next(
                r for r in payload["evidence"] if r["reference"]["file"] == "README.md"
            )
            valid["root_relations"][0]["evidence_ids"] = [doc["id"]]
            return schema.model_validate(valid)

    ctx = pipeline_context
    from app.adapters.artifacts import ArtifactStore
    from app.adapters.snapshot import snapshot_digest

    source = ArtifactStore().source(str(ctx["run_id"]))
    (source / "README.md").write_text("Development fixture business notes.\n")
    with Session(engine) as db:
        audit = db.get(AuditRun, ctx["run_id"])
        audit.snapshot_hash = snapshot_digest(source)
        db.add(audit)
        db.commit()
    run_scout(ctx)
    service = run_review(ctx, UngroundedRelation())
    result = service.repository.get(service.stage_id).result
    assert len(result["recommendations"]) == 2
    assert result["coverage_status"] == "completed"
    assert result["root_relations"] == []
    rejected = result["batches"][0]["rejected_root_relations"]
    assert len(rejected) == 1 and "源码证据" in rejected[0]["reason"]


def test_supplementary_finding_cannot_bypass_premise_checks(pipeline_context):
    class ExtraFinding(ReviewModel):
        def generate(self, purpose, payload, schema):
            valid = super().generate(purpose, payload, schema).model_dump(mode="json")
            target = payload["targets"][0]
            valid["new_findings"] = [
                {
                    "title": "A supplementary hypothesis needs verification",
                    "description": "Source location exists but necessary security premises are not checked.",
                    "weakness": "CWE-20",
                    "primary_location": {
                        key: target["location"][key] for key in ("file", "line")
                    },
                    "related_target": target["candidate_id"],
                    "evidence_ids": target["evidence_ids"],
                }
            ]
            return schema.model_validate(valid)

    service = run_review(pipeline_context, ExtraFinding())
    result = service.repository.get(service.stage_id).result
    with Session(engine) as db:
        added = db.exec(
            select(Candidate).where(
                Candidate.stage_id == service.stage.id, Candidate.origin == "ai"
            )
        ).one()
    assert added.model_assessment == "pending" and added.status == "pending"
    assert (
        next(r for r in result["recommendations"] if r["id"] == str(added.id))[
            "recommendation"
        ]
        == "pending"
    )
