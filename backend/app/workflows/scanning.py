from langgraph.graph import END, START, StateGraph

from app.services.scanning import ScanService
from app.workflows.state import ScanState


def build_scan_graph(service: ScanService, checkpointer=None):
    def database(state: ScanState) -> dict:
        service.create_database(state["run_id"])
        return {"database_ready": True}

    def scan(state: ScanState) -> dict:
        service.scan(state["run_id"])
        return {"sarif_ready": True}

    def evidence(state: ScanState) -> dict:
        service.save_findings(state["run_id"])
        return {"findings_saved": True}

    graph = StateGraph(ScanState)
    graph.add_node("codeql_database", database)
    graph.add_node("codeql_scan", scan)
    graph.add_node("persist_evidence", evidence)
    graph.add_edge(START, "codeql_database")
    graph.add_edge("codeql_database", "codeql_scan")
    graph.add_edge("codeql_scan", "persist_evidence")
    graph.add_edge("persist_evidence", END)
    return graph.compile(checkpointer=checkpointer)
