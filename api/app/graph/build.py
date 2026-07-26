from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

from app.graph.nodes.stub import stub_node
from app.graph.state import ReportState


def build_graph(checkpointer: BaseCheckpointSaver):
    """Compile the report graph.

    Phase 1 shape:   START -> stub -> END
    Phase 2 shape:   START -> {competitors, incumbents, market_signals, graveyard}
                           -> judge -> persist -> ingest -> END

    The fan-out arrives as additional `add_node` + `add_edge(START, ...)` calls;
    nothing here or in the runner needs restructuring.
    """
    builder = StateGraph(ReportState)
    builder.add_node("stub", stub_node)
    builder.add_edge(START, "stub")
    builder.add_edge("stub", END)
    return builder.compile(checkpointer=checkpointer)
