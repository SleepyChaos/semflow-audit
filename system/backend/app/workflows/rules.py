from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from app.adapters.node_timing import timed_node
from app.services.rule_synthesis import RuleSynthesis
from app.services.rules import RuleService


class RuleState(TypedDict, total=False):
    stage_id: str
    knowledge: list[dict]
    target: dict | None
    rule_id: str
    approved: bool
    validated: bool
    attempt: int
    draft_ok: bool
    draft_path: str
    candidate_digest: str
    materials_id: str
    materials_digest: str


def add_generation_nodes(graph, service):
    synthesis = RuleSynthesis(service)
    for name, operation in {
        "generate_rule": synthesis.propose,
        "compile_draft": synthesis.compile,
        "execute_development": synthesis.develop,
        "save_rule": synthesis.persist,
        "attempts_exhausted": synthesis.exhausted,
    }.items():
        graph.add_node(name, timed_node(service.directory, name, operation))
    graph.add_edge("generate_rule", "compile_draft")

    def retry_or(state, success):
        if state["draft_ok"]:
            return success
        return "generate_rule" if state["attempt"] < 2 else "attempts_exhausted"

    graph.add_conditional_edges(
        "compile_draft",
        lambda s: retry_or(s, "execute_development"),
        ["execute_development", "generate_rule", "attempts_exhausted"],
    )
    graph.add_conditional_edges(
        "execute_development",
        lambda s: retry_or(
            s,
            "project_single_rule"
            if service.stage.prompt_version in {"6", "7", "8"}
            else "save_rule",
        ),
        ["project_single_rule", "save_rule", "generate_rule", "attempts_exhausted"]
        if service.stage.prompt_version in {"6", "7", "8"}
        else ["save_rule", "generate_rule", "attempts_exhausted"],
    )
    if service.stage.prompt_version in {"6", "7", "8"}:
        graph.add_node(
            "project_single_rule",
            timed_node(
                service.directory, "project_single_rule", synthesis.replay_project
            ),
        )
        graph.add_conditional_edges(
            "project_single_rule",
            lambda s: retry_or(s, "save_rule"),
            ["save_rule", "generate_rule", "attempts_exhausted"],
        )
    graph.add_edge("attempts_exhausted", END)


def build_generation_graph(service):
    graph = StateGraph(RuleState)
    add_generation_nodes(graph, service)
    graph.add_edge(START, "generate_rule")
    graph.add_edge("save_rule", END)
    return graph.compile()


def build_rule_graph(service: RuleService, checkpointer=None):
    graph = StateGraph(RuleState)
    add_generation_nodes(graph, service)
    for name, operation in {
        "retrieve_knowledge": lambda _: service.retrieve(),
        "approve_fixtures": service.approve,
        "validate_rule": service.validate,
    }.items():
        graph.add_node(name, timed_node(service.directory, name, operation))
    graph.add_edge(START, "retrieve_knowledge")
    graph.add_edge("retrieve_knowledge", "generate_rule")
    graph.add_edge("save_rule", "approve_fixtures")
    graph.add_edge("approve_fixtures", "validate_rule")
    graph.add_edge("validate_rule", END)
    return graph.compile(checkpointer=checkpointer)
