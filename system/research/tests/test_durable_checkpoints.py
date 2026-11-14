"""Native LangGraph interrupt/resume must survive a fresh interpreter."""

import json
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError
from semflow_contracts.checkpoints import CheckpointBundle
from semflow_contracts.common import ArtifactRef
from semflow_contracts.errors import ResearchError
from semflow_research.runtime.artifacts import LocalArtifacts
from semflow_research.runtime.checkpoints import DurableSaver

SCRIPT = """
import json,sys
from pathlib import Path
from typing import TypedDict
from uuid import UUID
from langgraph.graph import StateGraph,START,END
from langgraph.types import Command,interrupt
from semflow_research.runtime.artifacts import LocalArtifacts
from semflow_research.runtime.checkpoints import DurableSaver
root=Path(sys.argv[1]); identifier=UUID(sys.argv[2]); mode=sys.argv[3]
class State(TypedDict, total=False):
    query: str
    approved: bool
def generate(state):
    with (root/'calls').open('a') as stream: stream.write('generate\\n')
    return {'query':'exact frozen QL bytes'}
def approval(state):
    approved=interrupt({'query':state['query']})
    return {'approved':approved}
saver=DurableSaver(artifacts=LocalArtifacts(root/'artifacts',identifier),execution_id=identifier,input_digest='a'*64,pointer=root/'checkpoint.json')
graph=StateGraph(State)
graph.add_node('generate',generate);graph.add_node('approval',approval)
graph.add_edge(START,'generate');graph.add_edge('generate','approval');graph.add_edge('approval',END)
graph=graph.compile(checkpointer=saver)
result=graph.invoke({} if mode=='pause' else Command(resume=True),{'configurable':{'thread_id':str(identifier)}})
print(json.dumps({'paused':bool(result.get('__interrupt__')),'approved':result.get('approved'),'query':result.get('query')}))
"""


def test_real_native_graph_resumes_without_regenerating_in_fresh_process(tmp_path):
    script, identifier = tmp_path / "graph.py", uuid4()
    script.write_text(SCRIPT)
    package_root = Path(__file__).resolve().parents[2]
    env = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join(
            str(package_root / item / "src") for item in ("contracts", "research")
        ),
        "HAYSTACK_TELEMETRY_ENABLED": "false",
    }

    def run(mode):
        result = subprocess.run(
            [sys.executable, str(script), str(tmp_path), str(identifier), mode],
            cwd=tmp_path,
            env=env,
            text=True,
            capture_output=True,
            check=True,
            timeout=30,
        )
        return json.loads(result.stdout)

    paused = run("pause")
    assert paused["paused"] and paused["query"] == "exact frozen QL bytes"
    resumed = run("resume")
    assert not resumed["paused"] and resumed["approved"] is True
    assert (tmp_path / "calls").read_text().splitlines() == ["generate"]


def test_checkpoint_engine_and_input_cannot_be_relabelled(tmp_path):
    identifier = uuid4()
    artifacts = LocalArtifacts(tmp_path / "artifacts", identifier)
    saver = DurableSaver(
        artifacts=artifacts,
        execution_id=identifier,
        input_digest="a" * 64,
        pointer=tmp_path / "checkpoint.json",
    )
    saver._persist()
    ref = ArtifactRef.model_validate_json((tmp_path / "checkpoint.json").read_bytes())
    original = CheckpointBundle.model_validate_json(artifacts.read(ref))
    with pytest.raises(ResearchError, match="different inputs"):
        DurableSaver(
            artifacts=artifacts,
            execution_id=identifier,
            input_digest="b" * 64,
            pointer=saver.pointer,
        )
    changed = original.model_dump(mode="json")
    changed["engine"] = "langgraph-checkpoint==0.0.0"
    invalid = artifacts.commit(
        json.dumps(changed).encode(), kind="checkpoint", schema_version=original.format
    )
    with pytest.raises(ValidationError):
        saver.restore(invalid)
