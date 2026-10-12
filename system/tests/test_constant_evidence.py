"""Value hints remain bounded and cannot execute a target or model mutable aliases."""

import pytest
from app.adapters.constant_evidence import evidence_clues, literal_clues


def test_arithmetic_branch_and_string_selector_have_exact_quotes():
    body = 'if 9 * 8 - 6 > 60:\n    pass\noptions = "XYZ"\nchoice = options[1]\n'
    clues = literal_clues(body)
    assert any(
        c["quote"] == "9 * 8 - 6 > 60" and c["possible_literal_values"] == ["True"]
        for c in clues
    )
    assert any(
        c["quote"] == "options[1]" and c["possible_literal_values"] == ["'Y'"]
        for c in clues
    )


def test_calls_and_imported_attributes_are_not_inferred(tmp_path):
    marker = tmp_path / "executed"
    source = f'from pathlib import Path\nif Path({str(marker)!r}).write_text("bad"):\n    pass\n'
    assert literal_clues(source) == []
    assert not marker.exists()


@pytest.mark.parametrize(
    "source",
    [
        'items=["safe","other"]\nitems.pop(0)\nx=items[0]\n',
        "import foreign\nx=foreign.secret[1]\n",
        "def choose(input):\n if input[0]:\n  pass\n",
        "if 2 ** 999999999 > 1:\n pass\n",
        'if ("x" * 999999999)[0] == "x":\n pass\n',
    ],
)
def test_mutations_dynamic_values_and_explosive_expressions_produce_no_proof(source):
    assert literal_clues(source) == []


def test_reference_coordinates_survive_source_window_offset():
    material = {
        "id": "actual-source",
        "kind": "code",
        "reference": {"file": "worker.py", "start_line": 40},
        "content": 'letters="abc"\nkey=letters[2]\n',
    }
    clue = evidence_clues([material])[0]
    assert clue["quote"] == "letters[2]" and clue["line"] == 41
    assert clue["file"] == "worker.py" and clue["evidence_id"] == "actual-source"
