from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from app.adapters.artifacts import ArtifactStore
from app.adapters.node_timing import timed_node
from app.services.review import ReviewService


class ReviewState(TypedDict, total=False):
    stage_id: str
    context: dict
    response: dict
    steps: int
    saved: bool


def build_review_graph(service: ReviewService, checkpointer=None):
    if service.stage.prompt_version in {"4", "5", "6", "7", "8", "9", "10", "11", "12"}:
        from app.workflows.unified_review import build_unified_review_graph

        return build_unified_review_graph(service, checkpointer)
    graph = StateGraph(ReviewState)
    directory = ArtifactStore().directory(service.stage_id)
    for name, operation in {
        "prepare_targets": lambda _: service.prepare(),
        "reason": service.reason,
        "gather_evidence": service.gather,
        "save_candidates": service.save,
    }.items():
        graph.add_node(name, timed_node(directory, name, operation))
    graph.add_edge(START, "prepare_targets")
    graph.add_edge("prepare_targets", "reason")
    graph.add_conditional_edges(
        "reason",
        lambda state: state["response"]["action"],
        {"tool": "gather_evidence", "final": "save_candidates"},
    )
    graph.add_edge("gather_evidence", "reason")
    graph.add_edge("save_candidates", END)
    return graph.compile(checkpointer=checkpointer)
