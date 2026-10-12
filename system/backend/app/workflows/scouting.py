from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from app.adapters.node_timing import timed_node


class ScoutState(TypedDict, total=False):
    stage_id: str
    map_hash: str
    stop_reason: str | None
    saved: bool


def build_scout_graph(service, checkpointer=None):
    graph = StateGraph(ScoutState)
    for name, operation in {
        "project_map": service.prepare,
        "inspect_windows": service.inspect,
        "save_coverage": service.finalize,
    }.items():
        graph.add_node(name, timed_node(service.directory, name, operation))
    graph.add_edge(START, "project_map")
    graph.add_edge("project_map", "inspect_windows")
    graph.add_edge("inspect_windows", "save_coverage")
    graph.add_edge("save_coverage", END)
    return graph.compile(checkpointer=checkpointer)
