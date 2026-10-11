from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from app.adapters.node_timing import timed_node


class ReportState(TypedDict, total=False):
    stage_id: str
    source_fingerprint: str
    material_fingerprint: str
    narrative: dict
    saved: bool


def build_report_graph(service, checkpointer=None):
    graph = StateGraph(ReportState)
    for name, operation in {
        "prepare_report": service.prepare,
        "write_chinese_report": service.generate,
        "save_report": service.save,
    }.items():
        graph.add_node(name, timed_node(service.directory, name, operation))
    graph.add_edge(START, "prepare_report")
    graph.add_edge("prepare_report", "write_chinese_report")
    graph.add_edge("write_chinese_report", "save_report")
    graph.add_edge("save_report", END)
    return graph.compile(checkpointer=checkpointer)
