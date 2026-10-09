"""Input inclusion, bounded investigation coverage and evidence integrity."""

import json
from uuid import UUID, uuid4

import pytest
from app.adapters.source_inventory import inspectable
from app.contracts.scouting import ScoutResponseV4
from app.core.db import engine
from app.domain.audit import AuditError
from app.persistence.audit_models import AuditRun
from app.persistence.stage_models import Candidate
from app.services.scout_inspection import compact_pages, validate_checks
from sqlmodel import Session, select

from tests.test_dual_discovery import HypothesisModel, run_scout
from tests.test_unified_review import run_review


class CheckedModel(HypothesisModel):
    def generate(self, purpose, payload, schema):
        result = super().generate(purpose, payload, schema)
        result.findings = [
            r for r in result.findings if r.primary_location.file.endswith(".ejs")
        ]
        for row in result.findings:
            row.weakness = "CWE-79"
            row.title = "Unescaped template output hypothesis"
            row.security_condition = (
                "Untrusted template data requires context-specific escaping."
            )
            row.observation = "The supplied template has a raw output expression."
        return result


@pytest.mark.parametrize(
    "pipeline_context",
    [
        {
            "app.py": "value = 1\n",
            "views/item.ejs": "<%- output.name %>\n",
            "config/security.yaml": "debug: true\n",
            ".env.production": "PLACEHOLDER=not-a-real-credential\n",
        }
    ],
    indirect=True,
)
def test_template_search_candidate_and_review_use_actual_evidence(pipeline_context):
    service = run_scout(pipeline_context, CheckedModel(), version="4")
    files = {
        p.relative_to(service.evidence.root).as_posix()
        for p in service.evidence.files()
    }
    assert "views/item.ejs" in files and "config/security.yaml" in files
    assert ".env.production" not in files
    assert "views/item.ejs" in service.evidence.search("output.name")["content"]
    with pytest.raises(AuditError):
        service.evidence.read(".env.production")
    with Session(engine) as db:
        scout = db.exec(
            select(Candidate).where(Candidate.stage_id == service.stage.id)
        ).one()
        assert scout.location["file"] == "views/item.ejs"
    review = run_review(pipeline_context, version="6", discover=False)
    result = review.repository.get(review.stage_id).result
    assert any(
        r["location"]["file"] == "views/item.ejs" for r in result["pool"]["entries"]
    )
    assert result["unreviewed_candidate_ids"] == []
    assert all(
        r["status"] == "inspected" and r["task_checks"]
        for r in service.repository.get(service.stage_id).result["units"]
    )


@pytest.mark.parametrize(
    "pipeline_context",
    [
        {
            "app.py": "value = 1\n",
            "routes/entry.py": "def route():\n    return handler()\n",
            "core/handler.py": "def handler():\n    return 1\n" * 70,
            "public/vendor.min.js": "x = 1;\n",
        }
    ],
    indirect=True,
)
def test_business_priority_keeps_generated_assets_as_explicit_gaps(pipeline_context):
    service = run_scout(pipeline_context, version="4", max_units=2)
    result = service.repository.get(service.stage_id).result
    project = json.loads((service.directory / "scout-map.json").read_text())
    assert [u["file"] for u in project["units"][:2]] == ["app.py", "routes/entry.py"]
    # Python mode does not enumerate standalone JS dependencies.
    assert result["coverage"]["business_coverage_status"] == "partial"
    assert result["coverage"]["task_coverage"]["status_counts"]["uninspected"] > 0


@pytest.mark.parametrize(
    "pipeline_context",
    [{f"module{i}.py": "value = 1\n" for i in range(8)}],
    indirect=True,
)
def test_equal_call_budget_covers_all_scheduled_windows(pipeline_context):
    model = CheckedModel()
    model.policy = {"max_calls": 8}
    service = run_scout(pipeline_context, model, version="4", max_units=8)
    assert model.usage["calls"] == 8
    assert all(p["finalize_required"] for p in model.seen)
    coverage = service.repository.get(service.stage_id).result["coverage"]
    assert coverage["inspected_windows"] == coverage["eligible_windows"] == 8


@pytest.mark.parametrize("pipeline_context", [{"app.py": "value = 1\n"}], indirect=True)
def test_omitted_checks_do_not_become_completed_inspection(pipeline_context):
    class Omitted(CheckedModel):
        def generate(self, purpose, payload, schema):
            result = super().generate(purpose, payload, schema)
            result.task_checks = result.task_checks[:-1]
            return result

    service = run_scout(pipeline_context, Omitted(), version="4")
    result = service.repository.get(service.stage_id).result
    assert result["coverage"]["inspected_windows"] == 0
    assert result["coverage"]["task_coverage"]["status_counts"]["uninspected"] == 8


def test_checks_reject_unread_evidence_and_unsubstantiated_not_applicable():
    context = {
        "inspection_tasks": [{"id": "authorization"}],
        "evidence": [{"id": str(uuid4())}],
    }
    data = {
        "action": "final",
        "task_checks": [
            {
                "task_id": "authorization",
                "status": "not_applicable",
                "reason": "This is only a configuration constant.",
                "evidence_ids": [],
            }
        ],
    }
    with pytest.raises(AuditError, match="实际证据"):
        validate_checks(ScoutResponseV4.model_validate(data), context)
    data["task_checks"][0]["evidence_ids"] = [str(uuid4())]
    with pytest.raises(AuditError, match="未读取"):
        validate_checks(ScoutResponseV4.model_validate(data), context)


def test_credential_and_dependency_workspaces_never_enter_inventory():
    for name in (
        ".env",
        "nested/.env.production",
        "config/vars.env",
        "vars.env.production",
        "node_modules/lib/index.js",
        ".venv/app.py",
    ):
        assert not inspectable(name, "javascript")
    assert inspectable("views/item.ejs", "javascript")
    assert inspectable("config/security.yml", "javascript")
    assert not inspectable("readme.md", "javascript")


def test_compaction_preserves_source_coverage_without_duplicate_bodies():
    def page(identifier, start, end):
        return {
            "id": identifier,
            "kind": "code",
            "reference": {"file": "app.py", "start_line": start, "end_line": end},
            "content": "actual fixture body",
        }

    result = compact_pages(
        [page("small", 1, 100), page("first", 1, 150), page("last", 151, 211)]
    )
    assert [r["id"] for r in result] == ["first", "last"]
    assert result[0]["reference"]["start_line"] == 1
    assert result[-1]["reference"]["end_line"] == 211


@pytest.mark.parametrize(
    "pipeline_context",
    [
        {
            "app.py": "value = 1\n",
            "routes/main.js": "router.post('/edit', edit)\n",
            "public/vendor.min.js": "library();\n",
            "views/edit.ejs": "<%- value %>\n",
        }
    ],
    indirect=True,
)
def test_v5_generated_sources_deferred_and_templates_investigated(pipeline_context):
    with Session(engine) as db:
        audit = db.get(AuditRun, pipeline_context["run_id"])
        audit.language = "javascript"
        db.add(audit)
        db.commit()
    service = run_scout(pipeline_context, CheckedModel(), version="5")
    result = service.repository.get(service.stage_id).result
    coverage = result["coverage"]
    assert coverage["business_coverage_status"] == "completed"
    assert coverage["eligible_windows"] == coverage["inspected_eligible_windows"] == 2
    assert coverage["status"] == "partial"
    assert coverage["deferred_windows"][0]["reason"] == "third_party_deferred"
    assert coverage["deferred_windows"][0]["file"] == "public/vendor.min.js"
    assert any(u["hypotheses"] for u in result["units"])


@pytest.mark.parametrize(
    "pipeline_context",
    [{"app.py": "value = 1\n", "views/item.ejs": "<%= output.name %>\n"}],
    indirect=True,
)
def test_template_counterevidence_can_exclude_without_erasing_candidate(
    pipeline_context,
):
    with Session(engine) as db:
        audit = db.get(AuditRun, pipeline_context["run_id"])
        audit.findings = []
        db.add(audit)
        db.commit()
    scout = run_scout(pipeline_context, CheckedModel(), version="5")

    class ExcludeTemplate(HypothesisModel):
        def generate(self, purpose, payload, schema):
            self.usage["calls"] += 1
            target = payload["targets"][0]
            ids = [
                r["id"]
                for r in payload["evidence"]
                if r["reference"].get("file") == "views/item.ejs"
            ]
            return schema.model_validate(
                {
                    "action": "final",
                    "candidate_assessments": [
                        {
                            "candidate_id": target["candidate_id"],
                            "assessment": "excluded",
                            "weakness": "CWE-79",
                            "reason": "The actual template uses the escaped output operator.",
                            "checked_premises": [
                                "Inspected the escaped output expression in the template."
                            ],
                            "evidence_ids": ids,
                            "counterevidence_ids": ids,
                        }
                    ],
                }
            )

    review = run_review(
        pipeline_context, ExcludeTemplate(), version="6", discover=False
    )
    result = review.repository.get(review.stage_id).result
    assert result["unreviewed_candidate_ids"] == []
    assert result["recommendations"][0]["recommendation"] == "excluded"
    with Session(engine) as db:
        original = db.exec(
            select(Candidate).where(Candidate.stage_id == scout.stage.id)
        ).one()
        assert original.status == "pending" and original.model_assessment == "pending"


@pytest.mark.parametrize(
    "pipeline_context",
    [{"app.py": "value = 1\n", "docker-compose.yml": "env_file: vars.env\n"}],
    indirect=True,
)
def test_forbidden_or_absent_environment_read_is_recoverable_not_inspected_content(
    pipeline_context,
):
    class MissingEnvironment(CheckedModel):
        def generate(self, purpose, payload, schema):
            if "latest_tool_observation" not in payload:
                self.usage["calls"] += 1
                return schema.model_validate(
                    {
                        "action": "tool",
                        "tool": {
                            "name": "read_source",
                            "arguments": {
                                "file": "vars.env",
                                "start_line": 1,
                                "end_line": 40,
                            },
                        },
                    }
                )
            assert (
                payload["latest_tool_observation"]["status"]
                == "source_unavailable_or_forbidden"
            )
            assert not any(
                r["reference"].get("file") == "vars.env" for r in payload["evidence"]
            )
            return super().generate(purpose, payload, schema)

    service = run_scout(pipeline_context, MissingEnvironment(), version="5")
    result = service.repository.get(service.stage_id).result
    assert result["coverage"]["business_coverage_status"] == "completed"
    assert all(u["task_checks"] for u in result["units"])


@pytest.mark.parametrize(
    "pipeline_context",
    [
        {
            "app.py": "value = 1\n",
            "views/item.ejs": "<%- output.name %>\n",
            "core/handler.py": "value = 1\n" * 155
            + "def list_users():\n    return database.users\n",
        }
    ],
    indirect=True,
)
def test_review7_reads_referenced_handler_ending_and_supplies_consistent_syntax(
    pipeline_context,
):
    class RelatedScout(CheckedModel):
        def generate(self, purpose, payload, schema):
            if (
                payload["unit"]["file"] == "views/item.ejs"
                and not payload["tool_trace"]
            ):
                self.usage["calls"] += 1
                return schema.model_validate(
                    {
                        "action": "tool",
                        "tool": {
                            "name": "read_source",
                            "arguments": {
                                "file": "core/handler.py",
                                "start_line": 1,
                                "end_line": 150,
                            },
                        },
                    }
                )
            result = super().generate(purpose, payload, schema)
            for row in result.findings:
                row.evidence_ids.extend(
                    UUID(r["id"])
                    for r in payload["evidence"]
                    if r["reference"].get("file") == "core/handler.py"
                )
            return result

    scout = run_scout(pipeline_context, RelatedScout(), version="5")
    with Session(engine) as db:
        audit = db.get(AuditRun, pipeline_context["run_id"])
        audit.findings = []
        db.add(audit)
        db.commit()
        original = db.exec(
            select(Candidate).where(Candidate.stage_id == scout.stage.id)
        ).one()
        selected = [str(original.id)]

    class CompleteHandler(HypothesisModel):
        def generate(self, purpose, payload, schema):
            self.usage["calls"] += 1
            assert any("def list_users" in r["content"] for r in payload["evidence"])
            assert (
                payload["framework_syntax_reference"][0]["facts"]["<%= expression %>"]
                == "HTML-escaped interpolation by default"
            )
            ids = [r["id"] for r in payload["evidence"] if r["kind"] == "code"]
            target = payload["targets"][0]
            citation = payload["citation_contract"]["target_source_ids"]
            assert citation[target["candidate_id"]] == target["evidence_ids"]
            assert all(
                identifier in ids for identifier in citation[target["candidate_id"]]
            )
            return schema.model_validate(
                {
                    "action": "final",
                    "candidate_assessments": [
                        {
                            "candidate_id": payload["targets"][0]["candidate_id"],
                            "assessment": "supported",
                            "weakness": "CWE-79",
                            "reason": "Actual source includes both the raw template and related handler ending.",
                            "checked_premises": [
                                "Related handler ending was read as actual source."
                            ],
                            "evidence_ids": ids,
                        }
                    ],
                }
            )

    review = run_review(
        pipeline_context,
        CompleteHandler(),
        version="7",
        scout_candidate_ids=selected,
        discover=False,
    )
    assert (
        review.repository.get(review.stage_id).result["unreviewed_candidate_ids"] == []
    )
