"""Algorithm extracted from app.workflows.repair_openhands.

Runtime dependencies are passed explicitly; no platform ORM or configuration.
Changes to JSON require checking the corresponding semflow_contracts/wire peer.
"""

"""OpenHands supplies candidates; platform nodes retain validation and acceptance."""
from langgraph.graph import END, START, StateGraph

from semflow_research.adapters.node_timing import timed_node
from semflow_research.repair.repair_openhands import OpenHandsRepair


def build_openhands_repair_graph(service, checkpointer=None, *, _kernel):
    from semflow_research.graphs.repair import RepairState

    repair = OpenHandsRepair(service, _kernel=_kernel)
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
