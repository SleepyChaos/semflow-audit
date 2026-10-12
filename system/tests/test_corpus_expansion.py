"""Reject changed official sources and avoid attributing group success to failed queries."""

import hashlib
from pathlib import Path

import pytest
from app.domain.audit import AuditError


@pytest.fixture(autouse=True)
def scripts_path(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "system/scripts"))


def entry(path, prefix, root):
    body = path.read_bytes()
    return {
        prefix + path.relative_to(root).as_posix(): {
            "sha": hashlib.sha1(
                b"blob " + str(len(body)).encode() + b"\0" + body
            ).hexdigest()
        }
    }


def test_pinned_source_verification_rejects_modified_library(tmp_path):
    from corpus_expansion_sources import verify

    source = tmp_path / "Library.qll"
    source.write_text("import python\n", newline="\n")
    tree = entry(source, "ql/lib/", tmp_path)
    assert verify(source, tmp_path, "ql/lib/", tree)[0] == "import python\n"
    source.write_text("import javascript\n", newline="\n")
    with pytest.raises(ValueError, match="differs from pinned tree"):
        verify(source, tmp_path, "ql/lib/", tree)


def test_complete_example_keeps_transitive_relative_helpers(tmp_path):
    from corpus_expansion_sources import local_modules

    folder = tmp_path / "Security" / "CWE-Test"
    folder.mkdir(parents=True)
    query = folder / "Test.ql"
    query.write_text("import First\nimport python\n", newline="\n")
    first, second = folder / "First.qll", folder / "Second.qll"
    first.write_text("private import Second\n", newline="\n")
    second.write_text("import First\nimport python\n", newline="\n")
    tree = {**entry(first, "ql/src/", tmp_path), **entry(second, "ql/src/", tmp_path)}
    modules = local_modules(query, tmp_path, tree)
    assert modules == {
        "Security/CWE-Test/First.qll": "private import Second\n",
        "Security/CWE-Test/Second.qll": "import First\nimport python\n",
    }
    second.write_text("import java\n", newline="\n")
    with pytest.raises(ValueError, match="differs from pinned tree"):
        local_modules(query, tmp_path, tree)


def test_failed_batch_checks_queries_individually(monkeypatch, tmp_path):
    import expand_rule_corpus as corpus

    monkeypatch.setattr(corpus, "OUTPUT", tmp_path)
    monkeypatch.setattr(corpus, "ROOT", tmp_path)
    monkeypatch.setattr(corpus, "search_paths", lambda pack: "fixed-test-packs")
    monkeypatch.setattr(corpus.CodeQLScanner, "version", lambda self: "fixed-cli")
    calls = []

    def command(args, log, timeout):
        calls.append(args)
        if len(calls) == 1 or args[-1].endswith("Bad.ql"):
            raise AuditError("compile failed")

    monkeypatch.setattr(corpus, "run_command", command)
    rows = [
        {"query_path": str(tmp_path / name), "metadata": {}}
        for name in ["Good.ql", "Bad.ql"]
    ]
    corpus.compile_group("python", rows)
    assert len(calls) == 3
    assert [r["metadata"]["validation"]["status"] for r in rows] == ["passed", "failed"]
    assert all(
        r["metadata"]["validation"]["development_status"] == "not_run" for r in rows
    )
