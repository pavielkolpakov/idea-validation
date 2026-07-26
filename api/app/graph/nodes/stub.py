"""Throwaway node. Phase 2 deletes this file and adds the four research nodes
plus the judge; everything around it (graph wiring, checkpointer, runner) stays.

It exists so Phase 1 can prove the async path end to end without spending a
cent on Perplexity or Anthropic.
"""

import asyncio

from langgraph.config import get_stream_writer

from app.graph.state import ReportState


async def stub_node(state: ReportState) -> dict:
    writer = get_stream_writer()

    writer({"step": "researching competitors"})
    await asyncio.sleep(1.5)

    writer({"step": "judging"})
    await asyncio.sleep(1.5)

    idea = state["idea"]
    report = {
        "verdict": "Stub report — no research was performed.",
        "score": 42,
        "subscores": {
            "novelty": 40,
            "market_size": 50,
            "competitive_intensity": 35,
            "timing": 45,
            "feasibility": 60,
        },
        "competitors": [
            {
                "name": "Example Corp",
                "domain": "example.com",
                "what_they_do": "Placeholder competitor for shape-checking the UI.",
                "funding_stage": "unknown",
            }
        ],
        "risks": ["This is stub output; the pipeline lands in Phase 2."],
        "differentiation": ["Replace stub_node with the real fan-out."],
        "echo": idea[:200],
    }

    writer({"step": "done"})
    return {"report": report, "score": report["score"]}
