"""Explicit synthetic tool fixtures shared by discovery boundary tests."""

import hashlib
import json
from uuid import uuid4

import pytest
from semflow_contracts.runs import validate_spec
from semflow_research.adapters.snapshot import snapshot_digest
from semflow_research.public.runtime import ToolSettings


@pytest.fixture
def settings(research_case, tmp_path):
    return ToolSettings(
        ARTIFACT_ROOT=research_case.ledger.root,
        CODEQL_BIN="codeql",
        CODEQL_PYTHON_BIN="python3",
        CODEQL_PACK_PATH=tmp_path / "packs",
        PYTHON_QUERY_PACK="codeql/python-all@test",
        JAVASCRIPT_QUERY_PACK="codeql/javascript-all@test",
        SCAN_TIMEOUT=20,
        CODEQL_THREADS=1,
        CODEQL_RAM=1024,
        VALIDATOR_PYTHON_IMAGE="test-image",
        VALIDATOR_JS_IMAGE="test-image",
        VALIDATOR_TIMEOUT=20,
        SEMANTIC_CONTEXT_CHARS=4000,
        SEMANTIC_REPAIR_MAX_CONTEXT_CHARS=8000,
        SEMANTIC_TOOL_LIMIT=3,
        REPAIR_SOURCE_TOOL_LIMIT=3,
        REPAIR_INITIAL_SOURCE_TOOL_LIMIT=3,
        REPAIR_MODEL_CALL_LIMIT=4,
        REPAIR_ATTEMPTS=1,
        REVIEW_QUERY_LIMIT=1,
        AI_BASE_URL="http://scripted.invalid/v1",
    )


def make_scan(research_case, settings):
    case = research_case
    pack = settings.CODEQL_PACK_PATH / "codeql/python-queries/test"
    pack.mkdir(parents=True)
    suite = pack / "test.qls"
    suite.write_text("- query: example.ql\n")
    (pack / "example.ql").write_text("import python\nfrom Call c select c\n")
    value = case.spec.model_dump(mode="json")
    value["execution_id"] = str(uuid4())
    value["inputs"].update(
        build_profile="none",
        suite={
            "name": "test.qls",
            "digest": hashlib.sha256(suite.read_bytes()).hexdigest(),
        },
    )
    value["inputs"]["query_pack"]["digest"] = snapshot_digest(pack)
    return validate_spec(value)


@pytest.fixture
def scanner(monkeypatch):
    from semflow_research.adapters.codeql.scanner import CodeQLScanner

    calls = []

    def create(self, source, output, log, plan):
        calls.append("database")
        output.mkdir()
        (output / "codeql-database.yml").write_text("scripted: true")
        log.write_text("Scripted tool boundary; no real CodeQL execution\n")

    def analyze(self, database, output, log, plan):
        calls.append("analyze")
        output.write_text(
            json.dumps(
                {
                    "version": "2.1.0",
                    "runs": [
                        {
                            "tool": {"driver": {"rules": []}},
                            "invocations": [{"executionSuccessful": True}],
                            "results": [
                                {
                                    "ruleId": "py/code-injection",
                                    "message": {"text": "Input reaches eval"},
                                    "locations": [
                                        {
                                            "physicalLocation": {
                                                "artifactLocation": {"uri": "app.py"},
                                                "region": {"startLine": 1},
                                            }
                                        }
                                    ],
                                }
                            ],
                        }
                    ],
                }
            )
        )

    monkeypatch.setattr(CodeQLScanner, "version", lambda self: "scripted-codeql")
    monkeypatch.setattr(CodeQLScanner, "create_database", create)
    monkeypatch.setattr(CodeQLScanner, "analyze", analyze)
    return calls
