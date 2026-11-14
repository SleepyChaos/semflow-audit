"""OpenHands supplies candidates; platform nodes retain validation and acceptance."""

from langgraph.graph import END, START, StateGraph

from app.adapters.node_timing import timed_node
from app.services.repair_openhands import OpenHandsRepair


def build_openhands_repair_graph(service, checkpointer=None):
    from app.workflows.repair import RepairState

    repair = OpenHandsRepair(service)
    graph = StateGraph(RepairState)
    for name, action in {
        "prepare_semantics": repair.semantic.prepare,
        "generate_with_openhands": repair.generate,
        "apply_isolated_candidate": repair.apply,
        "validate_candidate": repair.semantic.validate,
        "finalize_repair": repair.finalize,
    }.items():
        graph.add_node(name, timed_node(service.directory, name, action))
    graph.add_edge(START, "prepare_semantics")
    graph.add_edge("prepare_semantics", "generate_with_openhands")
    graph.add_edge("generate_with_openhands", "apply_isolated_candidate")
    graph.add_edge("apply_isolated_candidate", "validate_candidate")
    graph.add_edge("validate_candidate", "finalize_repair")
    graph.add_edge("finalize_repair", END)
    return graph.compile(checkpointer=checkpointer)
