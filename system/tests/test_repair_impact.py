"""Actual changed shared helpers expose read-only transitive caller obligations."""

from types import SimpleNamespace

from app.adapters.repair.impact import caller_obligations


def test_shared_helper_reads_two_levels_and_does_not_treat_names_as_resolved(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    original = "def match(value):\n    return value.lower()\ndef any_match(value):\n    return match(value)\ndef headers(value):\n    return any_match(value)\ndef resource(value):\n    return match(value)\n"
    (source / "core.py").write_text(original)
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    (candidate / "core.py").write_text(original.replace("value.lower()", "value"))
    observed = []

    def read(file, start, end):
        observed.append((file, start, end))
        lines = (source / file).read_text().splitlines()
        return {
            "id": f"actual-{len(observed)}",
            "kind": "code",
            "reference": {
                "file": file,
                "start_line": start,
                "end_line": min(end, len(lines)),
            },
            "content": "\n".join(lines[start - 1 : end]),
        }

    evidence = SimpleNamespace(
        root=source,
        files=lambda: list(source.rglob("*.py")),
        allowed=lambda file: source / file,
        read=read,
    )
    result = caller_obligations(evidence, [{"file": "core.py"}], candidate)
    assert result["changed_functions"] == ["match"]
    assert {row["caller"] for row in result["obligations"]} == {
        "any_match",
        "resource",
        "headers",
    }
    assert {row["evidence_id"] for row in result["obligations"]} == {
        row["id"] for row in result["evidence"]
    }
    assert all(row["content"] for row in result["evidence"])
    assert result["omitted_call_sites"] == 0
    assert "not resolved" in result["limitations"][0]
    assert (source / "core.py").read_text() == original
    limited = caller_obligations(
        evidence, [{"file": "core.py"}], candidate, max_windows=1
    )
    assert limited["omitted_call_sites"] == 2
    assert len(limited["obligations"]) == 1
