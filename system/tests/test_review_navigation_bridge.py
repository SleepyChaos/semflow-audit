"""Scripted workflow with mixed source languages and repeated gap requests."""

import pytest
from app.main import app
from app.runtime.scans import run_scan
from app.runtime.stages import run_stage
from app.services.stage_lifecycle import create_stage_run
from fastapi.testclient import TestClient
from semflow_research.domain.errors import AuditError
from sqlmodel import Session

from tests.research_bridge_cases import upload
from tests.test_research_review_bridge import ReviewModel


class NavigationModel(ReviewModel):
    fail_after_read = False
    bad_path = False

    def generate(self, purpose, payload, schema):
        self.contexts.append(payload)
        self.usage["calls"] += 1
        if self.bad_path and len(self.contexts) == 1:
            return schema.model_validate(
                {
                    "action": "tool",
                    "tool": {
                        "name": "read_source",
                        "arguments": {"file": "wrong/ui.js"},
                    },
                }
            )
        if self.bad_path and len(self.contexts) == 2:
            assert payload["latest_tool_observation"]["status"] == "unavailable"
        (target,) = payload["targets"]
        observed = {p["reference"].get("file") for p in payload["evidence"]}
        if self.fail_after_read and "assets/handlers/ui.js" in observed:
            raise AuditError(
                "Temporary model connection failure", code="provider_error"
            )
        symbol = (
            "inspectLocalPolicy"
            if "assets/handlers/ui.js" in observed
            else "submitForm"
        )
        return schema.model_validate(
            {
                "action": "final",
                "summary": "Local relationships remain to be investigated",
                "candidate_assessments": [
                    {
                        "candidate_id": target["candidate_id"],
                        "assessment": "insufficient",
                        "weakness": "CWE-95",
                        "security_property": target["security_property"],
                        "reason": "Local code needs additional review for caller trust.",
                        "evidence_ids": target["evidence_ids"],
                        "missing_premises": [
                            f"Locate {symbol}() and inspect its body."
                        ],
                        "runtime_unknowns": [
                            "Hosted application trust policy remains unverified"
                        ],
                        "premises": [
                            {
                                "premise": role,
                                "status": "missing",
                                "reason": f"An additional premise needs to be verified for {symbol}().",
                            }
                            for role in (
                                "operation",
                                "input_or_policy",
                                "unsafe_protection",
                            )
                        ],
                        "evidence_gaps": [
                            {
                                "gap_type": "repository",
                                "description": "Resolve local implementation",
                                "target_symbol": symbol,
                                "suggested_action": "find_symbol",
                            },
                            {
                                "gap_type": "repository",
                                "description": "Check guessed path",
                                "target_path": "does-not-exist.js",
                                "suggested_action": "read_source",
                            },
                            {
                                "gap_type": "runtime",
                                "description": "Check authenticated deployment",
                            },
                            {"meaningless": True},
                        ],
                        "detail": {
                            "title": "Review remains open",
                            "description": "The local input contract has yet to be located.",
                            "impact": "Operation exposure depends on the caller contract.",
                            "evidence_ids": target["evidence_ids"],
                            "exploitation": {
                                "status": "missing_preconditions",
                                "expected_result": "This is a source-only audit assessment.",
                            },
                        },
                    }
                ],
            }
        )


@pytest.mark.parametrize(
    ("steps", "fail_after_read"), [(1, False), (4, False), (4, True), (5, False)]
)
def test_cross_language_navigation_enters_next_review(
    bridge_case, scanner, monkeypatch, steps, fail_after_read
):
    db, owner, _, _ = bridge_case
    audit = upload(
        bridge_case,
        extra_sources={
            "templates/form.html": '<button onclick="submitForm()">Send</button>\n',
            "assets/handlers/ui.js": "function submitForm() { return true; }\n",
            "custom/policy_helpers.py": "def inspectLocalPolicy():\n    return False\n",
        },
    )
    assert run_scan(str(audit.id)).status == "completed"
    with Session(db) as session:
        stage = create_stage_run(
            session,
            audit.id,
            owner,
            "review",
            {
                "max_steps": steps,
                "supplement_insufficient": True,
            },
        )
    model = NavigationModel()
    model.fail_after_read = fail_after_read
    model.bad_path = steps == 5
    finished = run_stage(str(stage.id), kernel_model_factory=lambda: model)
    assert finished.status == "completed", finished.error
    (attempt,) = finished.result["candidate_review_attempts"]
    assert attempt["assessment"]["conclusion"] == "insufficient"
    (handoff,) = finished.result["candidate_handoffs"]
    if steps == 1 or fail_after_read:
        action = handoff["next_action"]
        if fail_after_read:
            assert action["kind"] == "retry_execution"
            assert len(model.contexts) == 2
        else:
            assert len(model.contexts) == 1
            assert action["kind"] == "gather_source"
            assert action["source_windows"][0]["file"] == "assets/handlers/ui.js"
        queued = []
        monkeypatch.setattr(
            "app.api.routes.stages.dispatch_stage",
            lambda stage, session: queued.append(stage.id),
        )
        candidate_id = attempt["candidate_ref"]["entity_id"]
        with TestClient(app) as client:
            response = client.post(f"/api/v1/candidates/{candidate_id}/continue-review")
        assert response.status_code == 201, response.text
        second = NavigationModel()
        retried = run_stage(str(queued[0]), kernel_model_factory=lambda: second)
        assert retried.status == "completed", retried.error
        continuation = retried.result["review_continuation"]
        if fail_after_read:
            assert any(
                item["location"]["path"] == "assets/handlers/ui.js"
                for item in continuation["cache"]["source"]
            )
        else:
            assert (
                continuation["new_source_evidence"][0]["file"]
                == "assets/handlers/ui.js"
            )
        assert any(
            page["reference"].get("file") == "assets/handlers/ui.js"
            for page in second.contexts[0]["evidence"]
        )
    else:
        assert len(model.contexts) == (4 if model.bad_path else 3)
        last = {
            page["reference"].get("file") for page in model.contexts[-1]["evidence"]
        }
        assert {"assets/handlers/ui.js", "custom/policy_helpers.py"} <= last
        assert handoff["next_action"]["kind"] == "collect_material"
        found = {
            gap["target_symbol"]
            for gap in attempt["evidence_gaps"]
            if gap["status"] == "found"
        }
        assert found == {"submitForm", "inspectLocalPolicy"}
    assert any(gap["gap_type"] == "runtime" for gap in attempt["evidence_gaps"])
