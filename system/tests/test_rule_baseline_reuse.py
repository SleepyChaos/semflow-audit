"""Baseline overlap is a coverage label, not a generation failure."""

import json
from types import SimpleNamespace

import pytest
from app.services.rule_synthesis import RuleSynthesis


@pytest.mark.parametrize(
    ("status", "accepted"),
    [
        ("already_covered", True),
        ("candidate_match_needs_confirmation", True),
        ("target_missed", False),
    ],
)
def test_project_replay_preserves_baseline_draft(
    tmp_path, monkeypatch, status, accepted
):
    import app.services.rule_project_validation as replay

    result = {
        "status": status,
        "matched_ids": [] if status == "target_missed" else ["hit"],
    }
    monkeypatch.setattr(replay, "replay_project", lambda *_: result)
    repository = SimpleNamespace(active=lambda *_: None, update=lambda *_, **__: None)
    service = SimpleNamespace(
        directory=tmp_path,
        stage_id="stage",
        repository=repository,
        provider=SimpleNamespace(usage={}),
        inputs=SimpleNamespace(candidate_id="target"),
    )
    pack = tmp_path / "draft-0"
    pack.mkdir()
    synthesis = RuleSynthesis(service)
    failures = []
    monkeypatch.setattr(
        synthesis,
        "_failure",
        lambda _, exc, __: failures.append(str(exc)) or {"draft_ok": False},
    )
    assert synthesis.replay_project({"attempt": 1}) == {"draft_ok": accepted}
    assert json.loads((pack / "project-replay.json").read_text()) == result
    assert bool(failures) is not accepted
