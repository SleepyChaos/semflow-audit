"""Runtime responses must not invalidate frozen code; code changes must."""

from scripts.benchmarks.benchmark_integrity import implementation_hashes


def test_runtime_responses_do_not_change_implementation_identity(tmp_path):
    source = tmp_path / "system/backend/app"
    source.mkdir(parents=True)
    (source / "service.py").write_text("VERSION = 1\n")
    original = implementation_hashes(tmp_path)
    response = tmp_path / "artifacts/runs/stage"
    response.mkdir(parents=True)
    (response / "model-call-1.response.txt").write_text("model output")
    assert implementation_hashes(tmp_path) == original
    (source / "service.py").write_text("VERSION = 2\n")
    assert implementation_hashes(tmp_path) != original


def test_added_or_removed_source_and_prompt_are_detected(tmp_path):
    source = tmp_path / "system/backend/app"
    source.mkdir(parents=True)
    prompt = source / "prompt.txt"
    prompt.write_text("prompt-v1")
    original = implementation_hashes(tmp_path)
    extra = source / "extra.py"
    extra.write_text("added")
    assert implementation_hashes(tmp_path) != original
    extra.unlink()
    assert implementation_hashes(tmp_path) == original
    prompt.unlink()
    assert implementation_hashes(tmp_path) != original
