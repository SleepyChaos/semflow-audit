from copy import deepcopy

import pytest
from app.domain.audit import AuditError
from app.services.rule_context_budget import fit_rule_context, model_characters


def context():
    return {
        "knowledge": [
            {
                "id": "api-1",
                "corpus": "reference",
                "retrieval_slot": ["reference"],
                "content": "declare API\n" * 300,
            },
            {
                "id": "api-2",
                "corpus": "reference",
                "retrieval_slot": ["reference"],
                "content": "optional API\n" * 1000,
            },
            {
                "id": "example-1",
                "corpus": "rule_example",
                "retrieval_slot": ["rule_example"],
                "content": "complete query { select source }",
            },
            {
                "id": "example-2",
                "corpus": "rule_example",
                "retrieval_slot": ["rule_example"],
                "content": "second complete query",
            },
        ],
        "semantic_inspection": {
            "evidence": [{"id": "source-1", "content": "project body\n" * 200}],
            "view": {
                "facts": [{"evidence_ids": ["api-1", "source-1"]}],
                "unknowns": ["runtime not proven"],
            },
        },
        "output_contract": {
            "knowledge_ids": ["api-1", "api-2", "example-1", "example-2"]
        },
    }


def test_selects_whole_optional_records_and_retains_source_facts_and_provenance():
    original = context()
    saved = deepcopy(original)
    fitted = fit_rule_context(original, 10000)
    assert model_characters(fitted) <= 10000
    assert original == saved
    assert fitted["semantic_inspection"] == original["semantic_inspection"]
    assert {row["id"] for row in fitted["knowledge"]} == {
        "api-1",
        "example-1",
        "example-2",
    }
    assert fitted["knowledge"][0] == original["knowledge"][0]
    assert fitted["context_selection"]["omitted_knowledge_ids"] == ["api-2"]
    assert fitted["output_contract"]["knowledge_ids"] == [
        "api-1",
        "example-1",
        "example-2",
    ]


def test_cited_records_cannot_be_removed_to_fake_context_success():
    original = context()
    original["semantic_inspection"]["view"]["facts"].append(
        {"evidence_ids": ["api-2", "example-2"]}
    )
    with pytest.raises(AuditError, match="原文未截断"):
        fit_rule_context(original, 10000)


def test_under_budget_context_keeps_identity_and_all_materials():
    original = context()
    assert fit_rule_context(original, model_characters(original)) is original


def test_failed_draft_text_is_readable_but_modified_candidate_is_rejected(tmp_path):
    import hashlib
    import json
    from uuid import uuid4

    from app.adapters.codeql.drafts import read_rule_drafts

    pack = tmp_path / "draft-0"
    pack.mkdir()
    candidate = {
        "title": "Draft detector",
        "strategy": "new_query",
        "coverage_analysis": "Unvalidated generated query for inspection only",
        "query": 'import python\nfrom Call c select c, "candidate"',
        "modules": {"Source.qll": "import python"},
        "knowledge_ids": [str(uuid4())],
        "positive": {"files": {"app.py": "eval(input())"}, "expected": []},
        "negative": {"files": {"app.py": 'print("safe")'}, "expected": []},
    }
    raw = json.dumps(candidate).encode()
    (pack / "candidate.json").write_bytes(raw)
    (pack / "generation-receipt.json").write_text(
        json.dumps({"candidate_digest": hashlib.sha256(raw).hexdigest()})
    )
    (pack / "diagnostic.json").write_text(
        json.dumps({"code": "compiler_error", "message": "actual compile failure"})
    )
    result = read_rule_drafts(tmp_path)
    assert result[0]["query"] == candidate["query"]
    assert result[0]["modules"] == candidate["modules"]
    assert result[0]["diagnostic"]["code"] == "compiler_error"
    (pack / "candidate.json").write_bytes(raw + b" ")
    with pytest.raises(AuditError, match="摘要不匹配"):
        read_rule_drafts(tmp_path)
