"""Full task identity, no-RAG isolation and interrupted-call replay protection."""

import json

import pytest
from scripts.benchmarks import cqllm_generation as generation
from scripts.benchmarks.cqllm_materials import freeze


def test_author_rows_not_collapsed_by_duplicate_query_id(tmp_path):
    manifest = freeze(tmp_path)
    assert manifest["rows"] == 298
    assert manifest["planned_tasks"] == 596
    assert manifest["unique_query_ids"] == 265
    assert len({t["id"] for t in manifest["tasks"]}) == 298
    assert freeze(tmp_path) == manifest


def test_uncommitted_model_task_cannot_silently_replay(tmp_path):
    directory = tmp_path / "arms/no_rag/row-0001"
    directory.mkdir(parents=True)
    (directory / "started.json").write_text("{}")
    with pytest.raises(RuntimeError, match="Uncommitted"):
        generation.generate({"id": "row-0001"}, "no_rag", tmp_path, {})


@pytest.mark.parametrize("version", ["cqllm-1", "cqllm-2"])
def test_no_rag_makes_no_retrieval_and_compiler_feedback_does_not_read_gold(
    tmp_path, monkeypatch, version
):
    calls = []

    class Model:
        def __init__(self):
            self.usage = {"calls": 0}
            self.records = []

        def generate(self, purpose, payload, schema):
            calls.append(dict(payload))
            return schema(
                query='/** @name test\n@description test\n@kind problem\n@problem.severity warning\n@precision medium\n@id audit/test\n*/\nimport python\nfrom Function f select f, "test"',
                modules={},
            )

    def compile_query(pack, log):
        if len(calls) == 1:
            log.write_text("development compiler error")
            raise RuntimeError("syntax")

    monkeypatch.setattr(generation, "provider", lambda *args: Model())
    monkeypatch.setattr(generation, "compile_query", compile_query)
    monkeypatch.setattr(
        generation,
        "retrieve_both",
        lambda *args, **kwargs: pytest.fail("no-RAG retrieved knowledge"),
    )
    config = {
        "prompt_version": version,
        "compiler_attempts": 2,
        "dependencies": {"codeql/python-all": {"version": "7.0.3"}},
    }
    task = {"id": "row-0001", "requirement": {"CWE-id": "CWE-89"}}
    result = generation.generate(task, "no_rag", tmp_path, config)
    assert result["status"] == "compiled"
    assert not result["first_compile_success"]
    assert calls[0]["knowledge"] == []
    assert "compiler_feedback" not in calls[0]
    assert calls[1]["compiler_feedback"] == "development compiler error"
    if version == "cqllm-2":
        assert calls[0]["output_contract"] == calls[1]["output_contract"]
        assert calls[0]["output_contract"]["generated_id"] == "audit/cqllm-row-0001"
    else:
        assert "output_contract" not in calls[0]
    assert "hidden" not in json.dumps(calls)
    generation.generate(task, "no_rag", tmp_path, config)
    assert len(calls) == 2


def test_contract_header_does_not_interpolate_untrusted_requirement(tmp_path):
    task = {"id": "row-0001", "requirement": {"Name": "*/ @id py/injected"}}
    contract = generation.output_contract(task)
    assert "injected" not in contract["query_header"]
    generation.prepare_query(
        tmp_path,
        "python",
        contract["query_header"] + 'import python\nfrom Function f select f, "test"',
        {},
        {"codeql/python-all": {"version": "4.0.10"}},
    )
    assert "@id audit/cqllm-row-0001" in (tmp_path / "generated.ql").read_text()
    with pytest.raises(ValueError, match="row identity"):
        generation.output_contract({"id": "row-0001\n*/"})


def test_pilot_selection_is_deterministic_and_not_based_on_results():
    from scripts.benchmarks.cqllm_prompt_pilot import select_tasks

    tasks = [
        {"id": f"row-{i:04}", "requirement": {"CWE-id": str(i % 5)}}
        for i in range(1, 21)
    ]
    selected = select_tasks(tasks, 4)
    assert selected == select_tasks(list(reversed(tasks)), 4)
    assert len({r["requirement"]["CWE-id"] for r in selected}) == 4
