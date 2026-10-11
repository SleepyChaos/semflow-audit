from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from app.adapters.node_timing import timed_node
from app.services.unified_review import UnifiedReview


class UnifiedReviewState(TypedDict, total=False):
    stage_id: str
    pool_hash: str
    saved: bool


def build_unified_review_graph(service, checkpointer=None):
    reviewer = UnifiedReview(service)
    graph = StateGraph(UnifiedReviewState)
    for name, operation in {
        "prepare_candidate_pool": reviewer.prepare,
        "verify_batches": reviewer.verify,
        "save_review": reviewer.finalize,
    }.items():
        graph.add_node(name, timed_node(reviewer.directory, name, operation))
    graph.add_edge(START, "prepare_candidate_pool")
    graph.add_edge("prepare_candidate_pool", "verify_batches")
    graph.add_edge("verify_batches", "save_review")
    graph.add_edge("save_review", END)
    return graph.compile(checkpointer=checkpointer)
