"""One stage lifecycle for workers, CLI runs and research graph entry points."""

import logging
from importlib import import_module
from inspect import signature

from langgraph.types import Command

from app.adapters.ai.provider import CompatibleModel
from app.persistence.stage_repository import StageCancelled, StageRepository
from app.runtime.checkpoints import stage_checkpoints

logger = logging.getLogger(__name__)


def stage_components(kind):
    modules = {
        "review": ("review", "ReviewService", "review", "build_review_graph"),
        "repair": ("repair", "RepairService", "repair", "build_repair_graph"),
        "rule": ("rules", "RuleService", "rules", "build_rule_graph"),
        "scout": ("scouting", "ScoutService", "scouting", "build_scout_graph"),
        "report": (
            "report_generation",
            "ReportService",
            "report",
            "build_report_graph",
        ),
    }
    service, name, workflow, builder = modules[kind]
    return (
        getattr(import_module(f"app.services.{service}"), name),
        getattr(import_module(f"app.workflows.{workflow}"), builder),
    )


def invoke_graph(stage, provider, resume, service_type, graph_builder):
    if service_type is None:
        service_type, graph_builder = stage_components(stage.kind)
    service = service_type(str(stage.id), provider)
    config = {"configurable": {"thread_id": str(stage.id)}, "recursion_limit": 60}
    inputs = (
        Command(resume={"approved": True}) if resume else {"stage_id": str(stage.id)}
    )
    # Historical benchmark-only subgraphs may intentionally stop before approval.
    # Keep their explicit graph selection; never silently resume an uncheckpointed graph.
    if "checkpointer" not in signature(graph_builder).parameters:
        if resume:
            raise ValueError("This research subgraph has no persistent resume boundary")
        return graph_builder(service).invoke(inputs, config=config)
    with stage_checkpoints() as saver:
        graph = graph_builder(service, checkpointer=saver)
        if resume:
            state = graph.get_state(config)
            if not state.next or not any(task.interrupts for task in state.tasks):
                raise ValueError("No interrupted checkpoint exists for this stage")
        return graph.invoke(inputs, config=config)


def run_stage(
    stage_id: str,
    resume: bool = False,
    *,
    provider_factory=None,
    service_type=None,
    graph_builder=None,
):
    repository = StageRepository()
    if not repository.claim(stage_id):
        return repository.get(stage_id)
    provider = None
    try:
        stage = repository.get(stage_id)
        if stage.kind == "verification":
            from app.services.repair_comparison import ComparisonService

            ComparisonService(stage_id).run()
        else:
            provider = (provider_factory or CompatibleModel)()
            if hasattr(provider, "bind_stage"):
                provider.bind_stage(stage_id, stage.prompt_version)
            if stage.kind == "candidate_translation":
                from app.services.candidate_localization import translate_candidates

                translate_candidates(stage_id, provider)
            elif stage.kind == "verification_suite":
                from app.services.verification_suites import SuiteService

                SuiteService(stage_id, provider).run()
            else:
                result = invoke_graph(
                    stage, provider, resume, service_type, graph_builder
                )
                if result.get("__interrupt__"):
                    repository.update(
                        stage_id,
                        status="awaiting_confirmation",
                        phase="awaiting_fixture_approval",
                    )
    except StageCancelled:
        logger.info("Stage cancelled: %s", stage_id)
    except Exception as exc:
        logger.exception("Stage failed: %s", stage_id)
        try:
            repository.update(
                stage_id,
                status="failed",
                error=str(exc)[:1000],
                result={
                    **repository.get(stage_id).result,
                    "failure": {
                        "code": getattr(exc, "code", "internal_error"),
                        "type": type(exc).__name__,
                    },
                },
                usage=provider.usage if provider else {},
            )
        except StageCancelled:
            pass
    return repository.get(stage_id)
