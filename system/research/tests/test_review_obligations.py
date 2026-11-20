from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

from semflow_research.discovery.review_gap_planner import plan_gaps
from semflow_research.discovery.review_python_behavior import inspect_behavior
from semflow_research.runtime import review_memory


def workspace(tmp_path: Path, sources: dict[str, str]):
    for name, body in sources.items():
        p = tmp_path / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
    return SimpleNamespace(
        root=tmp_path,
        allowed=lambda name: tmp_path / name,
        source_context=SimpleNamespace(snapshot_hash="fixture"),
    )


def page(path, source):
    return {
        "id": str(uuid4()),
        "kind": "code",
        "content": source,
        "reference": {
            "file": path,
            "start_line": 1,
            "end_line": len(source.splitlines()),
        },
    }


def test_cache_reuses_host_witness_but_never_reuses_a_model_quote_as_proof(monkeypatch):
    old_id, new_id = uuid4(), uuid4()
    snapshot_id = uuid4()
    digest = "a" * 64
    location = {
        "snapshot_id": snapshot_id,
        "path": "main.py",
        "start_line": 1,
        "end_line": 3,
        "file_sha256": digest,
    }
    loc = SimpleNamespace(**location)
    prior_ref = SimpleNamespace(entity_id=old_id)
    unresolved = SimpleNamespace(status="unverified", evidence_refs=(prior_ref,))
    verified = SimpleNamespace(
        status="supported",
        role="propagation",
        required_fact="The same value is returned.",
        verifier="python_direct_flow",
        detail="The value is copied without transformation.",
        evidence_refs=(prior_ref,),
    )
    seed = SimpleNamespace(
        previous_execution_id=uuid4(),
        attempt=SimpleNamespace(premises=(), obligations=(unresolved, verified)),
        code_evidence=(
            SimpleNamespace(location=loc, content="excerpt", evidence_id=old_id),
        ),
    )
    key = review_memory.ReviewMemoryIdentity(
        snapshot_id=snapshot_id,
        source_digest=digest,
        subject_digest=digest,
        analysis_digest=digest,
    )
    prior = object()
    spec = SimpleNamespace(inputs=SimpleNamespace(policy=SimpleNamespace(version="3")))
    context = SimpleNamespace(
        spec=spec, root="unused", artifacts=SimpleNamespace(read=lambda _: b"content")
    )
    service = SimpleNamespace(
        evidence=SimpleNamespace(
            allowed=lambda _: None,
            record=lambda *args: {"id": str(new_id), "digest": digest},
        )
    )
    from semflow_contracts.common import SourceLocation

    seed.code_evidence[0].location = SourceLocation.model_validate(location)
    monkeypatch.setattr(review_memory, "specification", lambda *args, **kwargs: prior)
    monkeypatch.setattr(review_memory, "identity", lambda spec, seed: key)
    _, facts, receipt = review_memory.restore(context, service, seed)
    assert receipt.fact_hits == receipt.source_hits == 1
    assert receipt.fact_misses == 0
    assert [f["validation"] for f in facts] == ["host_verified"]
    assert [UUID(ref) for ref in facts[0]["evidence_ids"]] == [new_id]
    monkeypatch.setattr(
        review_memory,
        "identity",
        lambda spec, seed: (
            key
            if spec is prior
            else key.model_copy(update={"analysis_digest": "b" * 64})
        ),
    )
    _, facts, receipt = review_memory.restore(context, service, seed)
    assert not facts
    assert receipt.source_hits == receipt.fact_misses == 1
    assert receipt.invalidation_reasons == ("analysis_digest",)


def test_runtime_label_does_not_hide_local_configuration(tmp_path):
    ev = workspace(tmp_path, {"core/middleware.py": "class RequestCheck:\n    pass\n"})
    plan = plan_gaps(
        {
            "candidate_id": str(uuid4()),
            "assessment": "insufficient",
            "runtime_unknowns": ["Whether middleware applies to this handler"],
            "evidence_gaps": [
                {
                    "gap_type": "runtime",
                    "description": "Inspect middleware configuration",
                }
            ],
        },
        ev,
        (),
        host_navigation=True,
    )
    assert [w.file for _, w in plan.windows] == ["core/middleware.py"]
    assert any(g.gap_type == "runtime" for g in plan.gaps)


def test_process_shell_selection_is_cited_without_confirming_a_flow(tmp_path):
    for argument, expected in (
        ("", "default_off"),
        (", shell=False", "explicit_off"),
        (", shell=True", "explicit_on"),
        (", **options", None),
    ):
        call = 'subprocess.run(["example"]' + argument + ")"
        source = "import subprocess\n\ndef invoke(options):\n    " + call + "\n"
        ev = workspace(tmp_path, {"proc.py": source})
        cited = page("proc.py", source)
        target = {"file": "proc.py", "line": 4}
        result = inspect_behavior(
            ev, target, [cited], call, "input_injection", "CWE-78"
        )
        assert result.shell_selection == expected
        assert not result.direct_flow and result.effect == "unverified"
        if expected:
            assert result.refs == (cited["id"],)
        no_import_page = {
            **cited,
            "reference": {"file": "proc.py", "start_line": 4, "end_line": 4},
            "content": "    " + call,
        }
        assert (
            inspect_behavior(
                ev, target, [no_import_page], call, "input_injection", "CWE-78"
            ).shell_selection
            is None
        )

    shadow = "import subprocess\n\ndef invoke(subprocess):\n    subprocess.run(['example'])\n"
    ev = workspace(tmp_path, {"proc.py": shadow})
    assert (
        inspect_behavior(
            ev,
            {"file": "proc.py", "line": 4},
            [page("proc.py", shadow)],
            "subprocess.run(['example'])",
            "input_injection",
            "CWE-78",
        ).shell_selection
        is None
    )


def test_shell_option_observation_does_not_turn_a_candidate_into_a_verdict(tmp_path):
    from semflow_research.discovery.review_obligations import verify_obligations

    source = (
        "import subprocess\n\ndef invoke(parameters):\n    subprocess.run(parameters)\n"
    )
    ev = workspace(tmp_path, {"proc.py": source})
    cited = page("proc.py", source)
    assessment = SimpleNamespace(
        weakness="CWE-78",
        security_property="input_injection",
        premises=[
            SimpleNamespace(
                premise="operation",
                quote="subprocess.run(parameters)",
                reason="A real source call is cited.",
                evidence_ids=[cited["id"]],
            )
        ],
        assessment="supported",
        detail=SimpleNamespace(),
        evidence_gaps=[],
        missing_premises=[],
        runtime_unknowns=[],
    )
    obligations = verify_obligations(
        SimpleNamespace(evidence=ev),
        assessment,
        {"location": {"file": "proc.py", "line": 4}},
        [cited],
        require_refutation=True,
    )
    assert assessment.assessment == "insufficient"
    assert (
        next(x for x in obligations if x["role"] == "effect")["status"] == "unverified"
    )
    observed = next(x for x in obligations if x["role"] == "process_shell_mode")
    assert observed["status"] == "supported"
    assert observed["evidence_ids"] == [cited["id"]]


def test_imported_stub_requires_cited_body_and_ignores_dynamic_shadow(tmp_path):
    app = "from helper import Writer\n\ndef endpoint(value):\n    Writer.emit(value)\n"
    helper = "class Writer:\n    @staticmethod\n    def emit(value):\n        pass\n"
    ev = workspace(tmp_path, {"app.py": app, "helper.py": helper})
    caller, callee = page("app.py", app), page("helper.py", helper)
    scope = {"file": "app.py", "line": 4}
    result = inspect_behavior(
        ev, scope, [caller, callee], "Writer.emit(value)", "other", "CWE-532"
    )
    assert result.effect == "refuted"
    assert set(result.refs) == {caller["id"], callee["id"]}
    assert (
        inspect_behavior(
            ev, scope, [caller], "Writer.emit(value)", "other", "CWE-532"
        ).effect
        == "unverified"
    )
    shadow = app.replace("    Writer.emit", "    Writer = factory()\n    Writer.emit")
    ev = workspace(tmp_path, {"app.py": shadow})
    result = inspect_behavior(
        ev,
        {"file": "app.py", "line": 5},
        [page("app.py", shadow), callee],
        "Writer.emit(value)",
        "other",
        "CWE-532",
    )
    assert result.effect == "unverified"


def test_locally_constructed_instance_has_a_noop_only_with_bound_receiver(tmp_path):
    source = "from .helpers import Writer\n\ndef show(value):\n    w = Writer(value)\n    w.emit(value)\n"
    helpers = "class Writer:\n    def __init__(self, value):\n        self.value = value\n    def emit(self, value):\n        pass\n"
    ev = workspace(tmp_path, {"pkg/views.py": source, "pkg/helpers.py": helpers})
    pages = [page("pkg/views.py", source), page("pkg/helpers.py", helpers)]
    result = inspect_behavior(
        ev,
        {"file": "pkg/views.py", "line": 5},
        pages,
        "w.emit(value)",
        "security_logging",
        "CWE-532",
    )
    assert result.effect == "refuted"
    ambiguous = source.replace(
        "    w.emit(value)", "    configure(w)\n    w.emit(value)"
    )
    ev = workspace(tmp_path, {"pkg/views.py": ambiguous, "pkg/helpers.py": helpers})
    result = inspect_behavior(
        ev,
        {"file": "pkg/views.py", "line": 6},
        [page("pkg/views.py", ambiguous), pages[1]],
        "w.emit(value)",
        "security_logging",
        "CWE-532",
    )
    assert result.effect == "unverified"


def test_small_direct_html_flow_can_be_verified(tmp_path):
    source = (
        "from flask import Flask, request\n"
        "app = Flask(__name__)\n"
        "@app.get('/')\n"
        "def index():\n"
        "    name = request.args['name']\n"
        "    return f'<p>{name}</p>'\n"
    )
    ev = workspace(tmp_path, {"app.py": source})
    target = {"file": "app.py", "line": 6}
    assert inspect_behavior(
        ev,
        target,
        [page("app.py", source)],
        "return f'<p>{name}</p>'",
        "output_encoding",
        "CWE-79",
    ).direct_flow
    sanitized = source.replace("{name}", "{escape(name)}")
    ev = workspace(tmp_path, {"app.py": sanitized})
    assert not inspect_behavior(
        ev,
        target,
        [page("app.py", sanitized)],
        "return f'<p>{escape(name)}</p>'",
        "output_encoding",
        "CWE-79",
    ).direct_flow
