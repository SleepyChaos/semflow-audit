"""Algorithm extracted from app.workflows.rules.

Runtime dependencies are passed explicitly; no platform ORM or configuration.
Changes to JSON require checking the corresponding semflow_contracts/wire peer.
"""

from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from semflow_research.adapters.node_timing import timed_node
from semflow_research.rules.rule_synthesis import RuleSynthesis
from semflow_research.rules.rules import RuleService


class RuleState(TypedDict, total=False):
    execution_id: str
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


def add_generation_nodes(graph, service, *, _kernel):
    synthesis = RuleSynthesis(service, _kernel=_kernel)
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
            if _kernel.spec.inputs.development.project_replay
            else "save_rule",
        ),
        ["project_single_rule", "save_rule", "generate_rule", "attempts_exhausted"]
        if _kernel.spec.inputs.development.project_replay
        else ["save_rule", "generate_rule", "attempts_exhausted"],
    )
    if _kernel.spec.inputs.development.project_replay:
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


def build_generation_graph(service, *, _kernel):
    graph = StateGraph(RuleState)
    add_generation_nodes(graph, service, _kernel=_kernel)
    graph.add_edge(START, "generate_rule")
    graph.add_edge("save_rule", END)
    return graph.compile()


def build_rule_graph(service: RuleService, checkpointer=None, *, _kernel):
    graph = StateGraph(RuleState)
    add_generation_nodes(graph, service, _kernel=_kernel)
    for name, operation in {
        "retrieve_knowledge": lambda _: service.retrieve(),
        "approve_fixtures": service.approve,
        "validate_rule": service.validate,
    }.items():
        graph.add_node(name, timed_node(service.directory, name, operation))
    graph.add_edge(START, "retrieve_knowledge")
    graph.add_edge("retrieve_knowledge", "generate_rule")
    graph.add_edge(
        "save_rule",
        "approve_fixtures"
        if _kernel.spec.inputs.acceptance.fixture_validation
        else END,
    )
    graph.add_conditional_edges(
        "approve_fixtures",
        lambda s: "validate_rule" if s["approved"] else END,
        ["validate_rule", END],
    )
    graph.add_edge("validate_rule", END)
    return graph.compile(checkpointer=checkpointer)
