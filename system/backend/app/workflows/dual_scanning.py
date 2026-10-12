from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from app.adapters.node_timing import timed_node


class DualScanState(TypedDict, total=False):
    run_id: str
    codeql_outcome: dict
    scout_outcome: dict
    joined: bool


def build_dual_scan_graph(service, checkpointer=None):
    graph = StateGraph(DualScanState)

    def measured(name, operation):
        def invoke(state):
            return timed_node(
                service.artifacts.directory(state["run_id"]), name, operation
            )(state)

        return invoke

    for name, operation in {
        "codeql_branch": service.codeql,
        "independent_scout": service.scout,
        "join_discovery": service.join,
    }.items():
        graph.add_node(name, measured(name, operation))
    graph.add_edge(START, "codeql_branch")
    graph.add_edge(START, "independent_scout")
    graph.add_edge(["codeql_branch", "independent_scout"], "join_discovery")
    graph.add_edge("join_discovery", END)
    return graph.compile(checkpointer=checkpointer)
