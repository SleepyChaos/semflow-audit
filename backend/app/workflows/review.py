from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from app.services.review import ReviewService


class ReviewState(TypedDict, total=False):
    stage_id: str
    context: dict
    response: dict
    steps: int
    saved: bool


def build_review_graph(service: ReviewService, checkpointer=None):
    graph = StateGraph(ReviewState)
    graph.add_node("prepare_targets", lambda _: service.prepare())
    graph.add_node("reason", service.reason)
    graph.add_node("gather_evidence", service.gather)
    graph.add_node("save_candidates", service.save)
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
