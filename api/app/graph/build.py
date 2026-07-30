from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

from app.clients.judge import JudgeClient
from app.clients.perplexity import ResearchClient
from app.graph.nodes.judge import make_judge_node
from app.graph.nodes.prompts import RESEARCH_AGENTS
from app.graph.nodes.research import make_research_node
from app.graph.state import ReportState


def build_graph(
    checkpointer: BaseCheckpointSaver,
    research_client: ResearchClient,
    judge: JudgeClient,
):
    """Compile the report graph.

    START -> {competitors, incumbents, market_signals, graveyard} -> judge -> END

    Four separate nodes with static edges from START, deliberately not one node
    calling `asyncio.gather`: separate nodes are what let the checkpointer resume
    a partially-completed run, and what let a planner-driven `Send` fan-out drop
    in later without rewriting the graph.

    There is no `persist` node — the runner writes the final row. Nodes never
    touch the database; see app/graph/CLAUDE.md.

    Clients are injected rather than constructed here so tests can drive the
    whole pipeline with fakes and no API spend.
    """
    builder = StateGraph(ReportState)

    for agent in RESEARCH_AGENTS:
        node_name = f"research_{agent}"
        # No RetryPolicy here on purpose: research nodes never raise (they
        # degrade instead), so a node-level policy would be dead config. Retry
        # lives inside the node, around the client call. See research.py.
        builder.add_node(node_name, make_research_node(agent, research_client))
        builder.add_edge(START, node_name)
        builder.add_edge(node_name, "judge")

    builder.add_node("judge", make_judge_node(judge))
    builder.add_edge("judge", END)

    return builder.compile(checkpointer=checkpointer)
