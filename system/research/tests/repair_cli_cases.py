"""Scripted model and validator boundaries for fresh-process CLI gates."""

SCRIPT = r"""
import importlib.abc, sys, json, ast
from pathlib import Path
from types import SimpleNamespace
class NoPlatform(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'app','fastapi','celery','sqlmodel','pydantic_settings'}:
            raise RuntimeError('Forbidden platform import: '+fullname)
sys.meta_path.insert(0,NoPlatform())
from openai.types.chat import ChatCompletion
from semflow_research.adapters.ai import provider
from semflow_research.adapters.repair.verification_runner import parse_results
from semflow_research.runtime import suite_build, repair_verify
import semflow_research.adapters.repair.verification_runner as runner
import semflow_research.repair.repair_suite_checks as suite_checks
import semflow_research.repair.repair as native
IMAGE='sha256:'+'a'*64
runner.resolve_image=lambda image:IMAGE
repair_verify.resolve_image=lambda image:IMAGE
suite_checks.resolve_image=lambda image:IMAGE

def create(**kwargs):
    p=json.loads(kwargs['messages'][-1]['content'])['untrusted_analysis_material']
    phase=p.get('phase')
    if phase is None:
        body={'title':'Numeric policy tests','summary':'Reject expressions and preserve integer input', 'language':'python',
            'files':{'test_input.py':'import pytest, runpy\n\ndef test_security(monkeypatch):\n    monkeypatch.setattr("builtins.input", lambda: "1+1")\n    with pytest.raises(ValueError): runpy.run_path("/workspace/app.py")\n\ndef test_functional(monkeypatch):\n    monkeypatch.setattr("builtins.input", lambda: "2")\n    assert runpy.run_path("/workspace/app.py")["value"] == 2\n'},
            'cases':[{'name':'test_security','category':'security','candidate_ids':p['required_candidate_ids'],
                'input_description':'Expression input','expected_behavior':'Reject dynamic expression'},
                {'name':'test_functional','category':'functional','candidate_ids':[],
                'input_description':'Integer input','expected_behavior':'Preserve integer value'}], 'assumptions':[]}
    elif phase=='inspect_semantics':
        ev=next(e for e in p['evidence'] if e['kind']=='code')
        body={'action':'ready','project_overview':'Actual source reads external numeric input',
            'target_flow':'Input reaches dynamic evaluation', 'modification_semantics':'Use explicit integer conversion',
            'facts':[{'statement':'Actual source evaluates external input','state':'supported',
                'evidence_ids':[ev['id']],'category':'security','critical':True}]}
    elif phase=='propose_patch':
        body={'changes':[{'file':'app.py','old_text':'eval(input())','new_text':'int(input())',
            'reason':'Replace dynamic interpretation with explicit integer conversion'}],
            'summary':'Preserve numeric intent without evaluating expressions'}
    elif phase=='assess_patch_contract':
        body={'constraints':[{'fact_index':i,'status':'consistent','explanation':'Explicit conversion preserves the selected numeric policy',
            'evidence_ids':[p['evidence'][0]['id']]} for i in p['required_fact_indices']], 'callers':[],
            'limitation':'External model substitute; not an exploitation proof'}
    else:
        raise AssertionError(phase)
    return ChatCompletion(id='scripted',created=0,model='scripted',object='chat.completion',
        choices=[{'index':0,'finish_reason':'stop','message':{'role':'assistant','content':json.dumps(body)}}],
        usage={'prompt_tokens':100,'completion_tokens':50,'total_tokens':150})
provider.OpenAI=lambda **kwargs:SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)),base_url='http://scripted.invalid')
def syntax(workspace,language,profile,*,_kernel):
    ast.parse((workspace/'app.py').read_text())
    return {'status':'passed','profile':profile,'output':'Explicit external validator substitute; actual source AST parsed'}
native.validate_workspace=syntax
def run(workspace,tests,suite,image,directory,*,_kernel):
    directory.mkdir(parents=True)
    text=(workspace/'app.py').read_text()
    failure='<failure message="AssertionError: expression accepted"/>' if 'eval(' in text else ''
    return parse_results('<testsuite><testcase name="test_security">'+failure+'</testcase><testcase name="test_functional"/></testsuite>',1 if failure else 0,suite)
suite_checks.run_suite=run
repair_verify.run_suite=run
from semflow_cli.main import main
raise SystemExit(main(sys.argv[1:]))
"""
