"""Algorithm extracted from app.workflows.unified_review.

Runtime dependencies are passed explicitly; no platform ORM or configuration.
Changes to JSON require checking the corresponding semflow_contracts/wire peer.
"""

from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from semflow_research.adapters.node_timing import timed_node
from semflow_research.discovery.unified_review import UnifiedReview


class UnifiedReviewState(TypedDict, total=False):
    execution_id: str
    pool_hash: str
    saved: bool


def build_unified_review_graph(service, checkpointer=None, *, _kernel):
    reviewer = UnifiedReview(service, _kernel=_kernel)
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
