"""The real suite adapter retains parsed reports and original bytes after cleanup."""

import shutil
from types import SimpleNamespace
from uuid import uuid4

import pytest
from semflow_contracts.common import ArtifactRef
from semflow_contracts.errors import ResearchError
from semflow_contracts.modelio.verification import VerificationSuite
from semflow_research.adapters.repair import verification_runner as adapter
from semflow_research.runtime.artifacts import LocalArtifacts


def test_suite_adapter_freezes_actual_report_and_console_bytes(tmp_path, monkeypatch):
    suite = VerificationSuite(
        title="Actual report",
        summary="Parse and retain executed report evidence",
        language="python",
        files={
            "test_case.py": "def test_security(): pass\ndef test_functional(): pass\n"
        },
        cases=[
            {
                "name": "test_security",
                "category": "security",
                "candidate_ids": [uuid4()],
                "input_description": "Untrusted input",
                "expected_behavior": "Reject unsafe execution",
            },
            {
                "name": "test_functional",
                "category": "functional",
                "candidate_ids": [],
                "input_description": "Normal input",
                "expected_behavior": "Preserve normal value",
            },
        ],
    )
    workspace, tests, output = tmp_path / "source", tmp_path / "tests", tmp_path / "run"
    workspace.mkdir()
    tests.mkdir()
    # Substitute only Docker process responses. The adapter command construction,
    # report parsing and immutable evidence commit are the actual implementation.
    monkeypatch.setattr(
        adapter.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="", stderr=""),
    )
    xml = '<testsuite><testcase name="test_security"><failure message="AssertionError: unsafe expression"/></testcase><testcase name="test_functional"/></testsuite>'
    responses = iter(
        [
            {
                "exit_code": 1,
                "reason": None,
                "output": "real tool boundary fixture console",
            },
            {"exit_code": 0, "reason": None, "output": xml},
        ]
    )
    monkeypatch.setattr(
        adapter, "execute_bounded", lambda *args, **kwargs: next(responses)
    )
    artifacts = LocalArtifacts(tmp_path / "artifacts", uuid4())
    context = SimpleNamespace(
        settings=SimpleNamespace(VALIDATOR_TIMEOUT=30), artifacts=artifacts
    )
    result = adapter.run_suite(
        workspace, tests, suite, "sha256:" + "a" * 64, output, _kernel=context
    )
    assert result["status"] == "completed"
    assert result["cases"]["test_security"]["status"] == "assertion_failed"
    refs = [ArtifactRef.model_validate(ref) for ref in result["evidence_refs"]]
    shutil.rmtree(output)
    assert artifacts.read(refs[0]).decode() == xml
    assert artifacts.read(refs[1]) == b"real tool boundary fixture console"
    (artifacts.root / str(artifacts.execution_id) / refs[0].path).write_text(
        "altered report"
    )
    with pytest.raises(ResearchError, match="Artifact bytes"):
        artifacts.read(refs[0])
