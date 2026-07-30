"""The judge node: four dossiers in, one structured scored report out.

Citations are the subtle part. Before the judge is called, every dossier's source
URLs are flattened into one deterministic table and the dossiers are rendered with
`[n]` markers appended. The judge can only emit integers into that table, so a
fabricated URL is not a failure mode that exists here — and an index that doesn't
resolve fails the run rather than rendering as a broken link.
"""

import logging
from collections.abc import Awaitable, Callable

from langgraph.config import get_stream_writer

from app.clients.judge import JudgeClient
from app.graph.nodes.prompts import JUDGE_PROMPT, JUDGE_SYSTEM, RESEARCH_AGENTS
from app.graph.schema import validate_citation_indices
from app.graph.state import ReportState

log = logging.getLogger(__name__)


def build_citation_table(dossiers: list[dict]) -> tuple[list[str], dict[str, list[int]]]:
    """Flatten dossier citations into one ordered, deduped table.

    Returns the table plus, per agent, the indices its own sources landed on —
    which is what lets each dossier be rendered with its own markers.
    """
    table: list[str] = []
    seen: dict[str, int] = {}
    per_agent: dict[str, list[int]] = {}

    # Sort by the canonical agent order so the table is stable regardless of
    # which research node happened to finish first.
    order = {agent: i for i, agent in enumerate(RESEARCH_AGENTS)}
    for dossier in sorted(dossiers, key=lambda d: order.get(d["agent"], 99)):
        indices = []
        for url in dossier.get("citations") or []:
            if url not in seen:
                seen[url] = len(table)
                table.append(url)
            indices.append(seen[url])
        per_agent[dossier["agent"]] = indices
    return table, per_agent


def render_dossiers(dossiers: list[dict], per_agent: dict[str, list[int]]) -> str:
    order = {agent: i for i, agent in enumerate(RESEARCH_AGENTS)}
    blocks = []
    for dossier in sorted(dossiers, key=lambda d: order.get(d["agent"], 99)):
        agent = dossier["agent"]
        if not (dossier.get("text") or "").strip():
            blocks.append(
                f"## {agent}\n\n"
                f"UNAVAILABLE — this research agent failed and returned nothing. "
                f"Do not treat its silence as evidence either way."
            )
            continue
        markers = " ".join(f"[{i}]" for i in per_agent.get(agent, []))
        suffix = f"\n\nSources for this dossier: {markers}" if markers else ""
        blocks.append(f"## {agent}\n\n{dossier['text']}{suffix}")
    return "\n\n".join(blocks)


def make_judge_node(client: JudgeClient) -> Callable[[ReportState], Awaitable[dict]]:
    async def node(state: ReportState) -> dict:
        writer = get_stream_writer()
        writer({"step": "judging"})

        dossiers = state.get("dossiers") or []
        degraded = sorted(state.get("degraded_agents") or [])

        # The floor: a report built on nothing is not a degraded report, it is
        # not a report. Everything short of this still ships.
        if all(not (d.get("text") or "").strip() for d in dossiers):
            raise RuntimeError("all research agents failed; no dossiers to judge")

        citations, per_agent = build_citation_table(dossiers)
        citation_index = (
            "\n".join(f"[{i}] {url}" for i, url in enumerate(citations))
            or "(no citations were returned by any agent)"
        )

        prompt = JUDGE_PROMPT.format(
            idea=state["idea"],
            target_user=(
                f"\nTarget user: {state['target_user']}" if state.get("target_user") else ""
            ),
            dossiers=render_dossiers(dossiers, per_agent),
            citation_index=citation_index,
        )

        report = await client.judge(JUDGE_SYSTEM, prompt)
        validate_citation_indices(report, len(citations))

        score = report.subscores.weighted_score()
        payload = report.model_dump()
        payload["degraded_agents"] = degraded
        payload["citations"] = citations

        return {"report": payload, "score": score, "citations": citations}

    return node
