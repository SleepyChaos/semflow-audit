"""Fresh platform-free discovery CLI process fixtures."""

import json
import subprocess
import sys

SCRIPT = r"""
import importlib.abc, json, os, sys
from pathlib import Path
class NoPlatform(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'app','fastapi','celery','sqlmodel','pydantic_settings'}:
            raise RuntimeError('Forbidden platform import: '+fullname)
sys.meta_path.insert(0, NoPlatform())
from pytest import MonkeyPatch
from semflow_cli.main import main
from semflow_research.adapters.codeql.scanner import CodeQLScanner
from semflow_research.adapters.ai.provider import CompatibleModel

with MonkeyPatch.context() as patch:
    def version(self): return 'scripted-codeql'
    def create(self, source, output, log, plan):
        output.mkdir(parents=True, exist_ok=True)
        (output/'codeql-database.yml').write_text('scripted: true')
        log.write_text('Scripted scanner boundary')
    def analyze(self, database, output, log, plan):
        output.write_text(json.dumps({'version':'2.1.0','runs':[{'tool':{'driver':{'rules':[]}},'invocations':[{'executionSuccessful':True}], 'results':[{'ruleId':'py/code-injection','message':{'text':'Input reaches eval'},'locations':[{'physicalLocation':{'artifactLocation':{'uri':'app.py'},'region':{'startLine':1}}}] }]}]}))
    patch.setattr(CodeQLScanner, 'version', version)
    patch.setattr(CodeQLScanner, 'create_database', create)
    patch.setattr(CodeQLScanner, 'analyze', analyze)
    def generate(self, purpose, payload, schema):
        if purpose == 'scout':
            return schema.model_validate({'action':'final','scope_summary':'Independent source window inspected','findings':[{'title':'Dynamic execution','weakness':'CWE-95','primary_location':{'file':'app.py','line':1},'security_condition':'Input may reach evaluation','observation':'Source calls eval on input','missing_premises':['Caller trust is unknown'],'evidence_ids':[payload['evidence'][0]['id']]}]})
        return schema.model_validate({'action':'final','summary':'Supplied hypotheses remain uncertain','candidate_assessments':[{'candidate_id':row['candidate_id'],'assessment':'insufficient','weakness':'CWE-95','reason':'Caller trust is unknown in the frozen source','evidence_ids':row['evidence_ids'],'missing_premises':['Caller trust is unknown']} for row in payload['targets']], 'new_findings':[], 'anchor_assessments':[], 'root_relations':[]})
    patch.setattr(CompatibleModel, 'generate', generate)
    code = main(sys.argv[1:])
raise SystemExit(code)
"""


def make_files(case, settings, tmp_path):
    pack = settings.CODEQL_PACK_PATH / "codeql/python-queries/test"
    pack.mkdir(parents=True, exist_ok=True)
    suite = pack / "test.qls"
    suite.write_text("- query: example.ql\n")
    (pack / "example.ql").write_text("import python\nfrom Call c select c\n")
    settings_values = settings.model_dump(mode="json")
    for name in ("AI_BASE_URL", "AI_MODEL", "AI_API_KEY", "ARTIFACT_ROOT"):
        settings_values.pop(name, None)
    resources = tmp_path / "resources.json"
    resources.write_text(
        json.dumps(
            {
                "profile_id": "discovery-cli",
                "settings": settings_values,
                "model_endpoints": {
                    "scripted": {"base_url": "http://scripted.invalid/v1"}
                },
            }
        )
    )
    policy = {
        "mode": "bounded",
        "max_calls": 8,
        "max_tokens": 100000,
        "max_seconds": 120,
        "per_call_timeout_seconds": 30,
        "tool_timeout_seconds": 30,
        "max_attempts": 1,
        "max_no_progress": 3,
        "max_context_chars": 40000,
        "resource_profile": "discovery-cli",
        "decision_policy": "human_only",
    }
    model = {
        "provider": "scripted-test",
        "model": "scripted",
        "endpoint_profile": "scripted",
        "output_schema_version": "1",
        "output_tokens": 2000,
    }
    options = tmp_path / "options.json"
    options.write_text(
        json.dumps(
            {
                "operation": "discover",
                "language": "python",
                "model": model,
                "policy": policy,
                "query_pack": "codeql/python-queries@test",
                "suite": "test.qls",
                "build_profile": "none",
                "scope_paths": ["app.py"],
                "inspection_paths": ["app.py"],
                "scheduling_profile": "full",
                "include_third_party": False,
                "window_lines": 100,
                "max_windows": 1,
                "max_steps_per_window": 1,
                "max_branch_calls": 1,
                "batch_size": 2,
                "max_batches": 1,
                "supplement_insufficient": False,
                "max_steps": 1,
                "max_context_chars": 40000,
                "required_branches": ["scan", "scout"],
                "scout_method_version": "1",
                "review_method_version": "4",
                "scout_prompt_version": 1,
                "review_prompt_version": 4,
            }
        )
    )
    # Keep the pack version expected by the options and resource capture aligned.
    (pack / "qlpack.yml").write_text(
        "name: codeql/python-queries\nversion: test\nlibrary: true\n"
    )
    (pack / "codeql-pack.lock.yml").write_text("dependencies: {}\n")
    return resources, options


def run(env, args, tmp_path):
    return subprocess.run(
        [sys.executable, "-c", SCRIPT, *args],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=45,
        check=False,
    )
