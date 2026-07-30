"""The four research nodes.

Failure is soft on purpose. `RetryPolicy` already absorbs the transient class, so
what reaches this handler is usually persistent (bad key, content filter, provider
outage) and re-running would not help. Hard-failing would also throw away the
three Perplexity calls that succeeded, and a report missing the graveyard dossier
is still a useful report. `degraded_agents` carries the honesty.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable

from langgraph.config import get_stream_writer

from app.clients.perplexity import Dossier, ResearchClient
from app.config import get_settings
from app.graph.nodes.prompts import RESEARCH_PROMPTS
from app.graph.state import ReportState

log = logging.getLogger(__name__)
_settings = get_settings()


def _format_target_user(target_user: str | None) -> str:
    return f"\nTarget user: {target_user}" if target_user else ""


async def _research_with_retry(client: ResearchClient, agent: str, prompt: str) -> Dossier:
    """Retry the transient class before giving up on this agent.

    This deliberately lives here rather than as a LangGraph `RetryPolicy` on the
    node. The node swallows its own exceptions to keep the run alive, so it never
    raises — and a RetryPolicy on a node that never raises never fires. Retry has
    to sit inside the node, underneath the fail-soft catch, or it does nothing.
    """
    attempts = max(1, _settings.research_retry_attempts)
    for attempt in range(1, attempts + 1):
        try:
            return await client.research(agent, prompt)
        except Exception:
            if attempt == attempts:
                raise
            delay = _settings.research_retry_base_delay_s * (2 ** (attempt - 1))
            log.warning(
                "research agent %s failed (attempt %s/%s), retrying", agent, attempt, attempts
            )
            if delay:
                await asyncio.sleep(delay)
    raise AssertionError("unreachable")


def make_research_node(
    agent: str, client: ResearchClient
) -> Callable[[ReportState], Awaitable[dict]]:
    async def node(state: ReportState) -> dict:
        writer = get_stream_writer()
        prompt = RESEARCH_PROMPTS[agent].format(
            idea=state["idea"],
            target_user=_format_target_user(state.get("target_user")),
        )

        try:
            dossier = await _research_with_retry(client, agent, prompt)
        except Exception as exc:  # noqa: BLE001 — a dead researcher must not kill the run
            log.exception("research agent %s failed", agent)
            dossier = Dossier(agent=agent, text="", error=f"{type(exc).__name__}: {exc}")

        # The runner counts these to render monotonic progress. Nodes announce
        # facts about themselves; the runner owns presentation and persistence.
        writer({"agent_done": agent})

        return {
            "dossiers": [vars(dossier)],
            "degraded_agents": [agent] if dossier.is_empty else [],
        }

    node.__name__ = f"research_{agent}"
    return node
