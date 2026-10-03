from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from app.services.rules import RuleService


class RuleState(TypedDict, total=False):
    stage_id: str
    knowledge: list[dict]
    target: dict | None
    rule_id: str
    approved: bool
    validated: bool


def build_rule_graph(service: RuleService, checkpointer=None):
    graph = StateGraph(RuleState)
    graph.add_node("retrieve_knowledge", lambda _: service.retrieve())
    graph.add_node("generate_rule", service.generate)
    graph.add_node("approve_fixtures", service.approve)
    graph.add_node("validate_rule", service.validate)
    graph.add_edge(START, "retrieve_knowledge")
    graph.add_edge("retrieve_knowledge", "generate_rule")
    graph.add_edge("generate_rule", "approve_fixtures")
    graph.add_edge("approve_fixtures", "validate_rule")
    graph.add_edge("validate_rule", END)
    return graph.compile(checkpointer=checkpointer)
