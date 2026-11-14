"""Suite generation and native feedback share actual public input/output codecs."""

import shutil

from semflow_contracts.runs import validate_spec
from semflow_research.public.repair import execute
from semflow_research.public.runtime import prepare
from semflow_research.public.suites import read

from research.tests.native_cases import repair_spec

IMAGE = "sha256:" + "a" * 64


def build_spec(case):
    value = repair_spec(case).model_dump(mode="json")
    behavior = case.artifacts.commit(
        b"Reject dynamic expression input while preserving integer conversion",
        kind="materials",
        schema_version="semflow.requested-behavior/1",
        media_type="text/plain",
    )
    value.update(
        operation="build_suite",
        inputs={
            "targets": value["inputs"]["targets"],
            "requested_behavior": behavior.model_dump(mode="json"),
            "runtime_profile": value["policy"]["resource_profile"],
        },
    )
    value["implementation"]["method_version"] = "2"
    value["prompts"][0].update(role="verification_suite", version="2")
    return validate_spec(value)


def test_build_suite_freezes_actual_assertions_and_never_executes_them(
    research_case, settings, suite_model
):
    spec = build_spec(research_case)
    context = prepare(spec, root=research_case.ledger.root, settings=settings)
    result = execute(spec, context)
    assert result.execution_status == "completed", result.failure
    assert result.result.review_required is True and result.usage.calls == 1
    body = read(result.result.suite, root=context.root)
    assert body.definition.files["test_numeric.py"].startswith("import pytest, runpy")
    assert body.image_digest == IMAGE
    assert body.source_digest == spec.source.tree_sha256
    assert len(suite_model.calls) == 1
    shutil.rmtree(context.workspace)
    assert context.executions.inspect(spec.execution_id) == result


def test_native_selected_suite_reads_refs_after_generation_workspace_deleted(
    research_case,
    settings,
    suite_model,
    repair_model,
    syntax,
    monkeypatch,
    suite_runner,
):
    from semflow_research.adapters.ai import provider

    repair_factory = provider.OpenAI
    monkeypatch.setattr(provider, "OpenAI", suite_model.factory)
    built_spec = build_spec(research_case)
    built_context = prepare(
        built_spec, root=research_case.ledger.root, settings=settings
    )
    built = execute(built_spec, built_context)
    assert built.execution_status == "completed", built.failure
    shutil.rmtree(built_context.workspace)
    monkeypatch.setattr(provider, "OpenAI", repair_factory)
    value = repair_spec(research_case).model_dump(mode="json")
    value["inputs"]["targets"] = built_spec.inputs.targets.model_dump(mode="json")
    value["inputs"]["suite"] = built.result.suite.model_dump(mode="json")
    value["inputs"]["method_policy"].update(
        selected_suite_feedback=True, baseline_reuse=True
    )
    value["inputs"]["validation_plan"]["before_after"] = True
    spec = validate_spec(value)
    context = prepare(spec, root=research_case.ledger.root, settings=settings)
    result = execute(spec, context)
    assert result.execution_status == "completed", result.failure
    assert result.result.outcome == "checks_passed"
    assert (
        next(c for c in result.result.checks if c.kind == "before_after").status
        == "passed"
    )
    assert (
        suite_runner == ["value = eval(input())\n"] * 2 + ["value = int(input())\n"] * 2
    )
    assert repair_model == [
        "inspect_semantics",
        "propose_patch",
        "assess_patch_contract",
    ]
    assert (
        context.workspace
        / "suite-inputs"
        / str(built.result.suite.suite_id)
        / "tests/test_numeric.py"
    ).is_file()


def test_independent_verify_consumes_published_repair_and_suite_without_model(
    research_case,
    settings,
    suite_model,
    repair_model,
    syntax,
    suite_runner,
    monkeypatch,
):
    from uuid import uuid4

    from semflow_contracts.common import EntityRef
    from semflow_research.adapters.ai import provider

    repair_factory = provider.OpenAI
    monkeypatch.setattr(provider, "OpenAI", suite_model.factory)
    built_spec = build_spec(research_case)
    built_context = prepare(
        built_spec, root=research_case.ledger.root, settings=settings
    )
    built = execute(built_spec, built_context)
    assert built.execution_status == "completed", built.failure
    monkeypatch.setattr(provider, "OpenAI", repair_factory)
    value = repair_spec(research_case).model_dump(mode="json")
    value["inputs"]["targets"] = built_spec.inputs.targets.model_dump(mode="json")
    generation_spec = validate_spec(value)
    generation_context = prepare(
        generation_spec, root=research_case.ledger.root, settings=settings
    )
    generated = execute(generation_spec, generation_context)
    assert generated.execution_status == "completed", generated.failure
    value.update(
        execution_id=str(uuid4()),
        operation="verify",
        model=None,
        prompts=[],
        inputs={
            "repair": EntityRef(
                execution_id=generation_spec.execution_id,
                entity_id=generated.result.repair_id,
                bundle=generated.manifest,
            ).model_dump(mode="json"),
            "patch": generated.result.patch.model_dump(mode="json"),
            "patched_source": generated.result.patched_source.model_dump(mode="json"),
            "suite": built.result.suite.model_dump(mode="json"),
            "validation_plan": {"syntax": False, "before_after": True},
        },
    )
    value["implementation"]["method_version"] = "1"
    spec = validate_spec(value)
    shutil.rmtree(generation_context.workspace)
    shutil.rmtree(built_context.workspace)
    monkeypatch.setattr(
        provider,
        "OpenAI",
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("verification cannot use a model")
        ),
    )
    context = prepare(spec, root=research_case.ledger.root, settings=settings)
    result = execute(spec, context)
    assert result.execution_status == "completed", result.failure
    assert result.result.receipt.status == "passed"
    assert result.result.identity.before_tree_sha256 == spec.source.tree_sha256
    assert result.result.identity.patch_sha256 == generated.result.patch.sha256
    assert result.usage.calls == 0
    assert suite_runner == ["value = eval(input())\n", "value = int(input())\n"] * 2
