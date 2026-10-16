"""Generic policy, framework and module-navigation boundaries; no benchmark answers."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from app.adapters.local_imports import python_import_paths, python_web_entrypoint
from app.adapters.snapshot import snapshot_digest
from app.contracts.discovery_semantics import PremiseCheck
from app.domain.audit import AuditError
from app.services.discovery_context import bootstrap_files, validate_premises
from app.services.discovery_framework_facts import enrich_semantic_context


def test_relative_import_resolution_respects_scope(tmp_path):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg/security.py").write_text("def guard(): pass\n")
    (tmp_path / "pkg/private.py").write_text("private = True\n")
    (tmp_path / "pkg/__init__.py").write_text("")
    imports = python_import_paths(
        tmp_path,
        "pkg/handler.py",
        "from .security import guard\nfrom . import private\nimport os\n",
        {"pkg/security.py", "pkg/__init__.py"},
    )
    assert "pkg/security.py" in imports
    assert "pkg/private.py" not in imports
    assert "os.py" not in imports


def test_factory_entrypoint_uses_bound_alias_not_file_name():
    assert python_web_entrypoint(
        "from flask import Flask as Web\napplication = Web(__name__)\n"
    )
    assert python_web_entrypoint(
        "import flask as framework\napplication = framework.Flask(__name__)\n"
    )
    assert not python_web_entrypoint("application = Flask(__name__)\n")
    assert not python_web_entrypoint(
        "from unrelated import Flask\napplication = Flask(__name__)\n"
    )


def test_entrypoint_and_helpers_in_arbitrary_directories(tmp_path):
    (tmp_path / "domain").mkdir()
    (tmp_path / "domain/control.py").write_text("def check(): return True\n")
    (tmp_path / "unusual_entry.py").write_text(
        "from flask import Flask as Web\napi = Web(__name__)\n"
    )
    (tmp_path / "domain/worker.py").write_text("from domain.control import check\n")
    files = list(tmp_path.rglob("*.py"))
    evidence = SimpleNamespace(
        root=tmp_path,
        audit=SimpleNamespace(language="python", snapshot_hash=snapshot_digest(tmp_path)),
        files=lambda: files,
        allowed=lambda f: tmp_path / f,
    )
    material = {
        "kind": "code",
        "reference": {"file": "domain/worker.py"},
        "content": "from domain.control import check\n",
    }
    result = bootstrap_files(evidence, [material], modern=True)
    assert "unusual_entry.py" in result and "domain/control.py" in result


def test_framework_defaults_are_conditional_and_no_import_means_no_fact():
    context = {
        "evidence": [
            {
                "kind": "code",
                "reference": {"file": "controller.py"},
                "content": "from flask import make_response\n",
            }
        ]
    }
    result = enrich_semantic_context(context)
    assert result["framework_semantics"][0]["project_version"].startswith("unverified")
    assert "custom response_class" in " ".join(
        result["framework_semantics"][0]["facts"]
    )
    assert enrich_semantic_context({"evidence": []})["framework_semantics"] == []


@pytest.mark.parametrize(
    "prop",
    [
        "authentication",
        "authorization",
        "object_ownership",
        "rate_limiting",
        "security_logging",
    ],
)
def test_missing_policy_never_becomes_supported(prop):
    evidence_id = uuid4()
    code = {
        "kind": "code",
        "reference": {"file": "worker.py"},
        "content": 'def public_status(): return "OK"',
    }
    checks = [
        PremiseCheck(
            premise=role,
            status="established",
            reason="Actual source was read, but the business policy is not provided.",
            evidence_ids=[evidence_id],
            quote=code["content"],
            policy_basis="unknown",
        )
        for role in ("operation", "input_or_policy", "unsafe_protection")
    ]
    assessment = SimpleNamespace(
        security_property=prop, assessment="supported", premises=checks
    )
    target = {
        "security_property": prop,
        "required_premises": ["operation", "input_or_policy", "unsafe_protection"],
    }
    context = {
        "language": "python",
        "semantic_context_version": 2,
        "local_control_context": {"missing_modules": []},
    }
    with pytest.raises(AuditError, match="政策依据"):
        validate_premises(assessment, target, context, lambda _: [code])
    assessment.assessment = "insufficient"
    validate_premises(assessment, target, context, lambda _: [code])


def test_new_scout_graph_keeps_independence_and_semantic_context(pipeline_context):
    from tests.test_dual_discovery import HypothesisModel, run_scout

    model = HypothesisModel()
    service = run_scout(pipeline_context, model, version="8")
    assert service.repository.get(service.stage_id).status == "completed"
    assert model.seen and model.seen[0]["semantic_context_version"] == 2
    assert "static_value_clues" in model.seen[0]
    assert "static_alert" not in model.seen[0] and "targets" not in model.seen[0]


def test_new_review_graph_validates_actual_premises(pipeline_context):
    from tests.test_discovery_semantics import SemanticModel
    from tests.test_unified_review import run_review

    model = SemanticModel()
    service = run_review(pipeline_context, model, version="10", discover=False)
    stage = service.repository.get(service.stage_id)
    assert stage.status == "completed" and stage.result["recommendations"]
    assert not stage.result["unreviewed_candidate_ids"]
    assert model.seen[0]["semantic_context_version"] == 2
