"""Run the extracted algorithms through their real independent public boundary."""

import json
from uuid import uuid4

import pytest
from discovery_cases import make_scan
from semflow_contracts.bundles import (
    CandidateBundle,
    EvidenceBundle,
    StaticFindingBundle,
)
from semflow_contracts.runs import validate_spec
from semflow_research.public.discovery import execute
from semflow_research.public.runtime import prepare


def test_scan_exports_real_evidence_and_stable_static_identity(
    research_case, settings, scanner
):
    spec = make_scan(research_case, settings)
    context = prepare(spec, root=research_case.ledger.root, settings=settings)
    result = execute(spec, context)
    assert result.execution_status == "completed", result.failure
    candidates = CandidateBundle.model_validate_json(
        context.artifacts.read(result.result.candidates.artifact)
    ).records
    evidences = EvidenceBundle.model_validate_json(
        context.artifacts.read(result.result.evidence.artifact)
    ).records
    findings = StaticFindingBundle.model_validate_json(
        context.artifacts.read(result.result.static_findings.artifact)
    ).records
    assert candidates[0].primary_location.path == "app.py"
    assert candidates[0].static_finding_ref.entity_id == findings[0].finding_id
    assert findings[0].raw_id != str(findings[0].finding_id)
    assert candidates[0].evidence_refs[0].entity_id == evidences[0].evidence_id
    context.source.validate(evidences[0])
    assert context.artifacts.read(evidences[0].content) == b"value = eval(input())"
    assert execute(spec, context) == result  # Duplicate delivery cannot repeat tools.
    assert scanner == ["database", "analyze"]
    assert result.usage.calls == 0


def test_invalid_sarif_is_failed_instead_of_zero_findings(
    research_case, settings, scanner, monkeypatch
):
    from semflow_research.adapters.codeql.scanner import CodeQLScanner

    monkeypatch.setattr(
        CodeQLScanner,
        "analyze",
        lambda self, database, output, log, plan: output.write_text("{broken"),
    )
    spec = make_scan(research_case, settings)
    context = prepare(spec, root=research_case.ledger.root, settings=settings)
    result = execute(spec, context)
    assert result.execution_status == "failed" and result.failure.code == "parse_failed"
    assert result.result is None and result.completeness.status == "none"
    assert (context.baseline_directory / "results.sarif").read_text() == "{broken"


def test_pack_hash_mismatch_fails_before_any_external_execution(
    research_case, settings, scanner
):
    spec = make_scan(research_case, settings)
    (settings.CODEQL_PACK_PATH / "codeql/python-queries/test/example.ql").write_text(
        "tampered"
    )
    context = prepare(spec, root=research_case.ledger.root, settings=settings)
    result = execute(spec, context)
    assert result.failure.code == "integrity_error"
    assert scanner == []


def test_extracted_scout_graph_keeps_hypotheses_unconfirmed(
    research_case, settings, monkeypatch
):
    from openai.types.chat import ChatCompletion

    case = research_case
    value = case.spec.model_dump(mode="json")
    identifier = uuid4()
    prompt = case.artifacts.commit(
        b"Inspect the given source; preserve unknown premises.",
        kind="prompt",
        schema_version="prompt/1",
        media_type="text/plain",
    )
    value.update(
        execution_id=str(identifier),
        operation="scout",
        inputs={
            "window_policy": {
                "version": "1",
                "max_windows": 1,
                "max_steps_per_window": 1,
                "max_calls": 1,
            }
        },
        model={
            "provider": "scripted-test",
            "model": "scripted",
            "endpoint_profile": "scripted",
            "output_schema_version": "1",
            "output_tokens": 2000,
        },
        prompts=[
            {
                "role": "scout",
                "template_id": "scout",
                "version": "1",
                "content": prompt.model_dump(mode="json"),
                "sha256": prompt.sha256,
            }
        ],
    )
    value["implementation"]["method_version"] = "1"
    value["policy"].update(max_tokens=50000, max_context_chars=20000)
    spec = validate_spec(value)
    context = prepare(spec, root=case.ledger.root, settings=settings)

    def response(**kwargs):
        payload = json.loads(kwargs["messages"][-1]["content"])[
            "untrusted_analysis_material"
        ]
        evidence = payload["evidence"][0]
        body = {
            "action": "final",
            "scope_summary": "Source window inspected with unresolved trust boundary",
            "findings": [
                {
                    "title": "Untrusted eval input",
                    "weakness": "CWE-95",
                    "primary_location": {"file": "app.py", "line": 1},
                    "security_condition": "User controlled input may reach dynamic execution",
                    "observation": "The source calls eval on input",
                    "missing_premises": ["Caller trust boundary is not verified"],
                    "evidence_ids": [evidence["id"]],
                }
            ],
        }
        return ChatCompletion(
            id="scripted",
            created=0,
            model="scripted",
            object="chat.completion",
            choices=[
                {
                    "index": 0,
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": json.dumps(body)},
                }
            ],
            usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        )

    monkeypatch.setattr(context.model.client.chat.completions, "create", response)
    result = execute(spec, context)
    assert result.execution_status == "completed", result.failure
    rows = CandidateBundle.model_validate_json(
        context.artifacts.read(result.result.candidates.artifact)
    ).records
    assert len(rows) == 1 and rows[0].origin == "scout"
    hypothesis = json.loads(context.artifacts.read(rows[0].context))
    assert hypothesis["missing_premises"] == ["Caller trust boundary is not verified"]
    from semflow_research.state.models import Candidate

    assert context.records.get(Candidate, rows[0].candidate_id).status == "pending"
    assert result.usage.calls == 1 and result.usage.completeness == "complete"
    assert context.source.snapshot.tree_sha256 == case.snapshot.tree_sha256


def test_review_imports_exact_static_bundle_and_preserves_unknown_verdict(
    research_case, settings, scanner, monkeypatch
):
    from openai.types.chat import ChatCompletion
    from semflow_contracts.bundles import AssessmentBundle
    from semflow_research.runtime.bundle_io import import_targets
    from semflow_research.state.models import Candidate

    case = research_case
    scan_spec = make_scan(case, settings)
    scanned = execute(
        scan_spec, prepare(scan_spec, root=case.ledger.root, settings=settings)
    )
    prompt = case.artifacts.commit(
        b"Verify supplied hypotheses against source evidence.",
        kind="prompt",
        schema_version="prompt/1",
    )
    value = scan_spec.model_dump(mode="json")
    value.update(
        execution_id=str(uuid4()),
        operation="review",
        inputs={
            "targets": scanned.result.candidates.model_dump(mode="json"),
            "evidence": scanned.result.evidence.model_dump(mode="json"),
            "source_execution_ids": [str(scan_spec.execution_id)],
            "policy": {
                "version": "1",
                "batch_size": 1,
                "max_batches": 1,
                "supplement_insufficient": False,
                "max_steps": 1,
                "max_context_chars": 40000,
            },
        },
        model={
            "provider": "scripted-test",
            "model": "scripted",
            "endpoint_profile": "scripted",
            "output_schema_version": "1",
            "output_tokens": 2000,
        },
        prompts=[
            {
                "role": "review",
                "template_id": "review",
                "version": "4",
                "content": prompt.model_dump(mode="json"),
                "sha256": prompt.sha256,
            }
        ],
    )
    value["implementation"]["method_version"] = "4"
    value["policy"].update(max_tokens=100000, max_context_chars=40000)
    spec = validate_spec(value)
    context = prepare(
        spec,
        root=case.ledger.root,
        settings=settings,
        upstream=(scan_spec.execution_id,),
    )
    # Import twice, as a resumed receiver does; immutable inputs must not acquire
    # fresh timestamps or duplicate static findings on the second pass.
    imported, _ = import_targets(context, spec.inputs.targets, spec.inputs.evidence)
    import_targets(imported, spec.inputs.targets, spec.inputs.evidence)
    assert len(imported.source_records.get(spec.source.snapshot_id).findings) == 1

    def response(*, conclusion="insufficient", **kwargs):
        payload = json.loads(kwargs["messages"][-1]["content"])[
            "untrusted_analysis_material"
        ]
        target = payload["targets"][0]
        body = {
            "action": "final",
            "summary": "The source is visible, but caller trust is still unknown",
            "candidate_assessments": [
                {
                    "candidate_id": target["candidate_id"],
                    "assessment": conclusion,
                    "weakness": "CWE-95",
                    "reason": (
                        "Direct input flows to evaluation"
                        if conclusion == "supported"
                        else "Caller trust boundary is not established by these source lines"
                    ),
                    "evidence_ids": target["evidence_ids"],
                    "missing_premises": []
                    if conclusion == "supported"
                    else ["Caller trust boundary has not been verified"],
                    "checked_premises": ["Direct input flows to evaluation"]
                    if conclusion == "supported"
                    else [],
                }
            ],
            "new_findings": [],
            "anchor_assessments": [],
            "root_relations": [],
        }
        return ChatCompletion(
            id="scripted",
            created=0,
            model="scripted",
            object="chat.completion",
            choices=[
                {
                    "index": 0,
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": json.dumps(body)},
                }
            ],
            usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        )

    monkeypatch.setattr(context.model.client.chat.completions, "create", response)
    result = execute(spec, context)
    assert result.execution_status == "completed", result.failure
    assert result.result.coverage.status == "full"
    assessments = AssessmentBundle.model_validate_json(
        context.artifacts.read(result.result.assessments.artifact)
    ).records
    from semflow_research.public.discovery_results import read_result

    view = read_result(result.execution_id, root=case.ledger.root)
    (handoff,) = view.trace.state["candidate_handoffs"]
    assert handoff["candidate_id"] == str(assessments[0].candidate_ref.entity_id)
    assert handoff["state"] == "unresolved"
    (review_attempt,) = view.review_report.records
    assert review_attempt.execution_state == "completed"
    assert review_attempt.evidence_state == "unresolved"
    assert review_attempt.assessment == assessments[0]
    assert review_attempt.previous_candidate_ref is not None
    assert review_attempt.location.snapshot_id == spec.source.snapshot_id
    assert handoff["reason_code"] == "insufficient_evidence"
    assert handoff["evidence_ids"] == [
        str(ref.entity_id) for ref in assessments[0].evidence_refs
    ]
    from semflow_research.public.review_continuation import assemble, capture

    seed = capture(
        result.execution_id,
        assessments[0].candidate_ref.entity_id,
        source=spec.source,
        root=case.ledger.root,
    )
    assert seed.assessment == assessments[0]
    assert {row.evidence_id for row in seed.code_evidence} == {
        ref.entity_id for ref in assessments[0].evidence_refs
    }

    from semflow_contracts.errors import ResearchError

    with pytest.raises(ResearchError, match="snapshot changed"):
        capture(
            result.execution_id,
            seed.candidate.candidate_id,
            source=spec.source.model_copy(update={"snapshot_id": uuid4()}),
            root=case.ledger.root,
        )
    assert assessments[0].conclusion == "insufficient"
    assert assessments[0].unknown_premises == (
        "Caller trust boundary has not been verified",
    )
    candidates = CandidateBundle.model_validate_json(
        context.artifacts.read(result.result.candidates.artifact)
    ).records
    assert (
        candidates[0].static_finding_ref.bundle
        == scanned.result.static_findings.artifact
    )
    assert (
        context.records.get(Candidate, candidates[0].candidate_id).status == "pending"
    )

    retry = assemble(
        result.execution_id, seed.candidate.candidate_id, root=case.ledger.root
    )
    retry_value = retry.model_dump(mode="json")
    retry_value["inputs"]["policy"]["max_steps"] = 2
    retry = validate_spec(retry_value)
    retry_context = prepare(retry, root=case.ledger.root, settings=settings)
    second_inputs = []

    def second_response(**kwargs):
        payload = json.loads(kwargs["messages"][-1]["content"])[
            "untrusted_analysis_material"
        ]
        second_inputs.append(payload)
        assert len(payload["targets"]) == 1
        assert payload["prior_review"]["previous_candidate_id"] == str(
            seed.candidate.candidate_id
        )
        assert payload["prior_review"]["missing_premises"] == list(
            assessments[0].unknown_premises
        )
        completion = response(conclusion="supported", **kwargs)
        if len(second_inputs) == 1:
            assert {page["digest"] for page in payload["evidence"]} == {
                item.digest for item in seed.code_evidence
            }
            completion.choices[0].message.content = json.dumps(
                {
                    "action": "tool",
                    "tool": {"name": "search_source", "arguments": {"text": "eval"}},
                }
            )
        else:
            assert any(page["kind"] == "search" for page in payload["evidence"])
        return completion

    monkeypatch.setattr(
        retry_context.model.client.chat.completions, "create", second_response
    )
    second = execute(retry, retry_context)
    assert second.execution_status == "completed", second.failure
    assert second.execution_id != result.execution_id
    assert len(second_inputs) == 2
    second_view = read_result(second.execution_id, root=case.ledger.root)
    (reused,) = second_view.trace.state["review_continuation"]["reused_evidence"]
    assert reused["previous_evidence_id"] == str(seed.code_evidence[0].evidence_id)
    assert reused["evidence_id"] != reused["previous_evidence_id"]
    assert second_view.assessments[0].conclusion == "supported"
    assert second_view.assessments[0].unknown_premises == ()
    assert second_view.review_report.records[0].evidence_state == "validated_references"
    assert second_view.review_report.records[0].assessment == second_view.assessments[0]
    assert (
        second_view.candidates[0].derived_from.entity_id == seed.candidate.candidate_id
    )
    assert (
        read_result(result.execution_id, root=case.ledger.root).assessments
        == assessments
    )


def test_cancellation_before_first_step_publishes_stopped_receipt(
    research_case, settings, scanner
):
    from semflow_contracts.actions import ControlCommand
    from semflow_research.runtime.control import LocalControl

    case = research_case
    spec = make_scan(case, settings)
    context = prepare(spec, root=case.ledger.root, settings=settings)
    command = ControlCommand(
        command_id=uuid4(),
        execution_id=spec.execution_id,
        action="cancel",
        expected_revision=0,
        reason="Stop before external tools start",
    )
    control = LocalControl(case.ledger)
    control.request_cancel(command)
    control.request_cancel(command)
    with case.ledger._connect() as db:
        assert case.ledger._row(db, spec.execution_id)["status"] == "created"
    result = execute(spec, context)
    assert result.execution_status == "cancelled" and result.failure.code == "cancelled"
    assert scanner == []


def test_runtime_resource_snapshot_excludes_credentials_and_rejects_profile_drift(
    research_case, settings
):
    from pydantic import SecretStr
    from semflow_contracts.errors import ResearchError

    case = research_case
    spec = make_scan(case, settings)
    initial = settings.model_copy(
        update={"AI_API_KEY": SecretStr("private-resource-marker")}
    )
    context = prepare(spec, root=case.ledger.root, settings=initial)
    snapshot = context.artifacts.read(context.resources_snapshot)
    assert b"private-resource-marker" not in snapshot and b"AI_API_KEY" not in snapshot
    assert json.loads(snapshot)["CODEQL_BIN"] == "codeql"
    rotated = initial.model_copy(
        update={"AI_API_KEY": SecretStr("rotated-private-marker")}
    )
    assert (
        prepare(spec, root=case.ledger.root, settings=rotated).resources_snapshot
        == context.resources_snapshot
    )
    changed = initial.model_copy(update={"CODEQL_BIN": "different-codeql"})
    with pytest.raises(ResearchError, match="resource profile changed"):
        prepare(spec, root=case.ledger.root, settings=changed)
