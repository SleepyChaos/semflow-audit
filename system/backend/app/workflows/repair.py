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
    attempt: int
    context_hash: str
    proposal_hash: str
    applied: bool
    passed: bool
    diagnosis: dict


def build_repair_graph(service: RepairService, checkpointer=None):
    if service.stage.prompt_version in {"2", "3", "4"}:
        return build_semantic_repair_graph(service, checkpointer)
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


def build_semantic_repair_graph(service, checkpointer=None):
    from app.services.repair_semantics import SemanticRepair

    repair = SemanticRepair(service)
    graph = StateGraph(RepairState)
    for name, operation in {
        "prepare_semantics": repair.prepare,
        "propose_patch": repair.propose,
        "apply_candidate": repair.apply,
        "validate_candidate": repair.validate,
        "diagnose_failure": repair.diagnose,
        "refresh_understanding": repair.refresh_understanding,
        "finalize_repair": repair.finalize,
    }.items():
        graph.add_node(name, timed_node(service.directory, name, operation))
    graph.add_edge(START, "prepare_semantics")
    graph.add_edge("prepare_semantics", "propose_patch")
    graph.add_edge("propose_patch", "apply_candidate")
    graph.add_conditional_edges(
        "apply_candidate",
        lambda s: "validate_candidate" if s["applied"] else "diagnose_failure",
    )
    graph.add_conditional_edges(
        "validate_candidate",
        lambda s: "finalize_repair" if s["passed"] else "diagnose_failure",
    )

    def feedback(state):
        category = state["diagnosis"]["category"]
        if state["attempt"] >= repair.policy["repair_attempts"] or category in {
            "environment",
            "inconclusive",
        }:
            return "finalize_repair"
        return (
            "refresh_understanding" if category == "understanding" else "propose_patch"
        )

    graph.add_conditional_edges("diagnose_failure", feedback)
    graph.add_edge("refresh_understanding", "propose_patch")
    graph.add_edge("finalize_repair", END)
    return graph.compile(checkpointer=checkpointer)
