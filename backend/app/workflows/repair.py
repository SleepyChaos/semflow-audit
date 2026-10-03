from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from app.adapters.node_timing import timed_node
from app.services.repair import RepairService


class RepairState(TypedDict, total=False):
    stage_id: str
    proposal: dict
    allowed_paths: list[str]
    repair_id: str
    checks: dict
    saved: bool


def build_repair_graph(service: RepairService, checkpointer=None):
    graph = StateGraph(RepairState)
    for name, operation in {
        "plan_patch": lambda _: service.plan(),
        "apply_isolated_copy": service.apply,
        "validate_patch": service.validate,
        "save_validation": service.save,
    }.items():
        graph.add_node(name, timed_node(service.directory, name, operation))
    graph.add_edge(START, "plan_patch")
    graph.add_edge("plan_patch", "apply_isolated_copy")
    graph.add_edge("apply_isolated_copy", "validate_patch")
    graph.add_edge("validate_patch", "save_validation")
    graph.add_edge("save_validation", END)
    return graph.compile(checkpointer=checkpointer)
