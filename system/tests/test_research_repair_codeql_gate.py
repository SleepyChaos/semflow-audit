"""One opt-in synthetic Web repair: actual CodeQL baseline/rescan and Docker syntax."""

import hashlib
import json
import os
import shutil
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest
from app.core.audit_config import ROOT, audit_settings
from app.main import app
from app.persistence.audit_models import AuditRun
from app.persistence.stage_models import (
    Candidate,
    Decision,
    Evidence,
    RepairRecord,
    StageRun,
)
from app.research_bridge.models import ResearchBinding
from app.research_bridge.requests import research_root
from app.runtime.scans import run_scan
from app.runtime.stages import run_stage
from fastapi.testclient import TestClient
from openai.types.chat import ChatCompletion
from semflow_research.adapters.ai import provider
from semflow_research.public.runs import inspect
from sqlmodel import Session, select

from tests.research_bridge_cases import upload


@pytest.mark.parametrize("pipeline", ["rescan", "full"])
@pytest.mark.integration
@pytest.mark.skipif(
    os.environ.get("AUDIT_RUN_REAL_TOOLS") != "1",
    reason="explicit real local tools opt-in",
)
def test_web_native_rescan_uses_real_codeql_and_docker(
    bridge_case, repair_model, monkeypatch, pipeline
):
    source = bridge_case[3]
    content = (
        'from flask import Flask, request\napp = Flask(__name__)\n@app.get("/vulnerable")\ndef vulnerable():\n'
        '    return str(eval(request.args["code"]))\n@app.get("/safe")\ndef safe():\n    return request.args.get("code", "")\n'
    )
    (source / "app.py").write_text(content)
    monkeypatch.setattr(audit_settings, "CODEQL_BIN", "/opt/homebrew/bin/codeql")
    monkeypatch.setattr(
        audit_settings, "CODEQL_PYTHON_BIN", "/opt/homebrew/bin/python3.11"
    )
    monkeypatch.setattr(audit_settings, "CODEQL_PACK_PATH", ROOT / "artifacts/packs")
    monkeypatch.setattr(
        audit_settings, "PYTHON_QUERY_PACK", "codeql/python-queries@1.6.0"
    )
    monkeypatch.setattr(audit_settings, "CODEQL_THREADS", 1)
    monkeypatch.setattr(audit_settings, "CODEQL_RAM", 2048)
    monkeypatch.setattr(audit_settings, "SCAN_TIMEOUT", 180)
    monkeypatch.setattr(
        audit_settings,
        "VALIDATOR_PYTHON_IMAGE",
        os.environ["SEMFLOW_RESEARCH_VALIDATOR_IMAGE"],
    )
    audit = upload(bridge_case)
    with Session(bridge_case[0]) as session:
        current = session.get(AuditRun, audit.id)
        current.suite = "Security/CWE-094/CodeInjection.ql"
        session.add(current)
        session.commit()
    scanned = run_scan(str(audit.id))
    assert scanned.status == "completed", scanned.error
    assert [p["line"] for f in scanned.findings for p in f["locations"]] == [5]
    with Session(bridge_case[0]) as session:
        stage = StageRun(audit_id=audit.id, kind="manual_evidence", status="completed")
        session.add(stage)
        session.flush()
        excerpt = content.splitlines()[4]
        evidence = Evidence(
            stage_id=stage.id,
            audit_id=audit.id,
            kind="code",
            snapshot_hash=scanned.snapshot_hash,
            reference={"file": "app.py", "start_line": 5, "end_line": 5},
            content=excerpt,
            digest=hashlib.sha256(excerpt.encode()).hexdigest(),
        )
        session.add(evidence)
        session.flush()
        candidate = Candidate(
            audit_id=audit.id,
            stage_id=stage.id,
            static_finding_id=scanned.findings[0]["id"],
            origin="static",
            title="Dynamic evaluation",
            description="Flask request code is dynamically evaluated by the selected source line",
            status="confirmed",
            evidence_ids=[str(evidence.id)],
            identity_key="static:" + scanned.findings[0]["id"],
            weakness="CWE-94",
            location={"file": "app.py", "line": 5, "end_line": 5},
        )
        session.add(candidate)
        session.flush()
        session.add(
            Decision(
                candidate_id=candidate.id,
                actor_id=bridge_case[1],
                status="confirmed",
                reason="Explicit synthetic operator confirmation of the actual Flask source evidence",
                evidence_ids=candidate.evidence_ids,
            )
        )
        session.commit()
        candidate_id = candidate.id
    suite_id = None
    if pipeline == "full":
        test_source = """import sys, runpy, pytest
from types import SimpleNamespace

def load(monkeypatch, value):
    class App:
        def get(self, path):
            return lambda function: function
    request = SimpleNamespace(args={'code': value})
    monkeypatch.setitem(sys.modules, 'flask', SimpleNamespace(Flask=lambda name: App(), request=request))
    return runpy.run_path('/workspace/app.py')

def test_security(monkeypatch):
    handlers = load(monkeypatch, '1+1')
    with pytest.raises(ValueError):
        handlers['vulnerable']()

def test_functional(monkeypatch):
    handlers = load(monkeypatch, '2')
    assert handlers['vulnerable']() == '2'
    assert handlers['safe']() == '2'
"""
        repair_factory = provider.OpenAI

        def generate_suite(**kwargs):
            payload = json.loads(kwargs["messages"][-1]["content"])[
                "untrusted_analysis_material"
            ]
            body = {
                "title": "Flask numeric policy",
                "summary": "Reject expression evaluation and preserve numeric request behavior",
                "language": "python",
                "files": {"test_flask.py": test_source},
                "cases": [
                    {
                        "name": "test_security",
                        "category": "security",
                        "candidate_ids": payload["required_candidate_ids"],
                        "input_description": "Request code is expression 1+1",
                        "expected_behavior": "Numeric handler rejects expression input with ValueError",
                    },
                    {
                        "name": "test_functional",
                        "category": "functional",
                        "candidate_ids": [],
                        "input_description": "Numeric request code 2",
                        "expected_behavior": "Both selected and safe handlers return string 2",
                    },
                ],
                "assumptions": [
                    "The selected route is intended for numeric input; Flask request/application are unit-test scaffolds"
                ],
            }
            return ChatCompletion(
                id="suite-scripted",
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
                usage={
                    "prompt_tokens": 100,
                    "completion_tokens": 50,
                    "total_tokens": 150,
                },
            )

        monkeypatch.setattr(
            provider,
            "OpenAI",
            lambda **kwargs: SimpleNamespace(
                chat=SimpleNamespace(
                    completions=SimpleNamespace(create=generate_suite)
                ),
                base_url="http://scripted.invalid/v1",
            ),
        )
        monkeypatch.setattr("app.jobs.stages.execute_stage.delay", lambda *args: None)
        with TestClient(app) as client:
            response = client.post(
                f"/api/v1/audits/{audit.id}/verification-suites/generate",
                json={
                    "candidate_ids": [str(candidate_id)],
                    "requirements": "Preserve integer request inputs and reject expression evaluation",
                },
            )
            assert response.status_code == 201, response.text
            suite_id = UUID(response.json()["id"])
        built = run_stage(str(suite_id))
        assert built.status == "completed", (built.error, built.result)
        monkeypatch.setattr(provider, "OpenAI", repair_factory)
    factory = provider.OpenAI

    def model(**kwargs):
        client = factory(**kwargs)
        create = client.chat.completions.create

        def response(**kwargs):
            completion = create(**kwargs)
            body = json.loads(completion.choices[0].message.content)
            if "changes" in body:
                body["changes"][0].update(
                    old_text='eval(request.args["code"])',
                    new_text='int(request.args["code"])',
                )
                completion.choices[0].message.content = json.dumps(body)
            return completion

        client.chat.completions.create = response
        return client

    monkeypatch.setattr(provider, "OpenAI", model)
    monkeypatch.setattr("app.jobs.stages.execute_stage.delay", lambda *args: None)
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/audits/{audit.id}/repair",
            json={
                "candidate_ids": [str(candidate_id)],
                "allowed_paths": [],
                "validation_profile": "syntax",
                "rescan": True,
                **({"verification_suite_id": str(suite_id)} if suite_id else {}),
            },
        )
        assert response.status_code == 201, response.text
        stage_id = UUID(response.json()["id"])
    repaired = run_stage(str(stage_id))
    assert repaired.status == "completed", (repaired.error, repaired.result)
    if pipeline == "full":
        from app.persistence.stage_models import StageFollowup

        with Session(bridge_case[0]) as session:
            followup = session.exec(
                select(StageFollowup).where(StageFollowup.source_stage_id == stage_id)
            ).one()
            assert followup.status == "delivered", followup.error
            comparison_id = followup.target_stage_id
        compared = run_stage(str(comparison_id))
        assert compared.status == "completed", (compared.error, compared.result)
        assert compared.result["status"] == "passed", compared.result
        assert compared.usage["calls"] == 0
        assert all(
            case["before"]
            == ("assertion_failed" if case["category"] == "security" else "passed")
            and case["after"] == "passed"
            for case in compared.result["cases"]
        )
    with Session(bridge_case[0]) as session:
        record = session.exec(
            select(RepairRecord).where(RepairRecord.stage_id == stage_id)
        ).one()
        binding = session.exec(
            select(ResearchBinding).where(ResearchBinding.stage_id == stage_id)
        ).one()
        result = inspect(binding.execution_id, root=research_root())
        assert record.validation["syntax"]["status"] == "passed"
        assert record.validation["rescan"]["status"] == "passed", record.validation
        assert record.validation["rescan"]["findings"] == []
        assert record.status == "checks_passed" and record.accepted_by is None
        assert repair_model == [
            "inspect_semantics",
            "propose_patch",
            "assess_patch_contract",
        ]
        target = Path(os.environ["SEMFLOW_RESEARCH_GATE_REPORT"]) / str(
            binding.execution_id
        )
        target.mkdir(parents=True, exist_ok=False)
        shutil.copytree(research_root(), target / "research")
        (target / "receipt.json").write_text(result.model_dump_json(indent=2))
        (target / "record.json").write_text(record.model_dump_json(indent=2))
        if pipeline == "full":
            (target / "comparison.json").write_text(compared.model_dump_json(indent=2))
            assert record.validation["selected_suite"]["status"] == "passed"
            assert len(result.result.checks) >= 3
            assert any(
                len(c.checks[0].evidence) >= 5
                for c in result.result.checks
                if c.kind == "before_after"
            )
            with TestClient(app) as client:
                response = client.post(
                    f"/api/v1/repairs/{record.id}/accept",
                    json={
                        "test_reviewed": True,
                        "comparison_stage_id": str(comparison_id),
                        "reason": "Synthetic operator reviewed repeated real pytest results and the exact patch",
                    },
                )
                assert response.status_code == 200, response.text
                (target / "acceptance.json").write_text(response.text)
        (target / "scope.json").write_text(
            json.dumps(
                {
                    "scope": "one synthetic Flask source, real Web/worker/native/CodeQL baseline and rescan/Docker syntax/projection",
                    "substitutes": ["external model", "operator confirmation"],
                    "pipeline": pipeline,
                    "before_findings": scanned.findings,
                    "limits": "Real CodeQL/Docker syntax and repeated pytest before/after assertions; model/operator are explicit substitutes, Flask is a unit scaffold; no real model efficacy or complete project safety claim"
                    if pipeline == "full"
                    else "No real model efficacy or real external pytest comparison claim; syntax and static disappearance do not accept a patch",
                    "execution_id": str(binding.execution_id),
                    "stage_id": str(stage_id),
                    "input_digest": result.input_digest,
                },
                indent=2,
            )
        )
