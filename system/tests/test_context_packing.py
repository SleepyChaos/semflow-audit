"""Context recovery must retain evidence and independent candidate identities."""

from types import SimpleNamespace

from app.adapters.context_packing import context_size, fit_navigation
from app.adapters.snapshot import snapshot_digest
from app.services.discovery_context import bootstrap_files, property_for
from app.services.review_pool import batches, fit_batches


def test_navigation_trim_retains_bodies_and_proof_contract():
    context = {
        "evidence": [{"id": "actual", "kind": "code", "content": "unsafe()"}],
        "security_property_contract": {"proof": "actual quote required"},
        "project_map": {"names": ["navigation"] * 2000},
    }
    packed = fit_navigation(context, 1000)
    assert context_size(packed) < 1000
    assert packed["evidence"] == context["evidence"]
    assert packed["security_property_contract"] == context["security_property_contract"]
    assert "names" in context["project_map"]
    oversized = {"evidence": [{"content": "actual source" * 2000}]}
    assert context_size(fit_navigation(oversized, 1000)) > 1000


def entry(identity, file, weakness="CWE-89"):
    return {
        "candidate_id": identity,
        "origin": "static",
        "location": {"file": file, "line": 1},
        "weakness": weakness,
    }


def test_cohorts_do_not_cross_files_or_security_properties():
    entries = [entry("a", "a.py"), entry("b", "b.py"), entry("c", "b.py", "CWE-1004")]
    schedule = batches({"entries": entries}, 4, coherent_conditions=True)
    assert len(schedule) == 3
    assert {r["candidate_id"] for batch in schedule for r in batch} == {"a", "b", "c"}
    assert property_for(entries[-1]) == "secrets_config"


def test_oversized_batch_splits_without_dropping_evidence(monkeypatch):
    import app.services.review_pool as pool

    monkeypatch.setattr(
        pool,
        "batch_context",
        lambda service, entries: {
            "evidence": [{"content": "source" * 100} for _ in entries]
        },
    )
    service = SimpleNamespace(inputs=SimpleNamespace(max_context_chars=800))
    entries = [entry(str(i), "a.py") for i in range(4)]
    assert fit_batches(service, [entries]) == [[r] for r in entries]


def test_independent_demo_bootstrap_is_not_target_middleware(tmp_path):
    for file in ("app.py", "a/app.py", "a/view.py", "b/app.py"):
        path = tmp_path / file
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("value = 1\n")
    evidence = SimpleNamespace(
        root=tmp_path,
        files=lambda: list(tmp_path.rglob("*.py")),
        audit=SimpleNamespace(language="python", snapshot_hash=snapshot_digest(tmp_path)),
        allowed=lambda file: tmp_path / file,
    )
    files = bootstrap_files(
        evidence,
        [{"kind": "code", "reference": {"file": "a/view.py"}, "content": "value = 1"}],
        modern=True,
    )
    assert "a/app.py" in files and "app.py" in files
    assert "b/app.py" not in files
