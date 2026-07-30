"""Deterministic stand-ins for the paid clients.

These exist mainly to make failure reachable. The behaviours that matter most in
this pipeline are the degraded ones — one researcher down, all four down, a judge
that cites a source that doesn't exist — and provoking those against a real API
is not possible on demand.
"""

import asyncio

from app.clients.perplexity import Dossier
from app.graph.schema import Competitor, DifferentiationAngle, JudgeReport, Risk, Subscores


class FakeResearchClient:
    """Returns canned dossiers; raises for any agent named in `fail_agents`."""

    def __init__(
        self,
        fail_agents: set[str] | None = None,
        flaky_agents: dict[str, int] | None = None,
        delays: dict[str, float] | None = None,
    ) -> None:
        self.fail_agents = fail_agents or set()
        # agent -> how many times to fail before succeeding, for testing retry.
        self.flaky_agents = flaky_agents or {}
        # agent -> seconds to stall, so a test can observe intermediate progress.
        self.delays = delays or {}
        self.calls: list[str] = []

    async def research(self, agent: str, prompt: str) -> Dossier:
        self.calls.append(agent)
        if delay := self.delays.get(agent):
            await asyncio.sleep(delay)
        if agent in self.fail_agents:
            raise RuntimeError(f"simulated {agent} failure")
        if self.flaky_agents.get(agent, 0) > 0:
            self.flaky_agents[agent] -= 1
            raise TimeoutError(f"simulated transient {agent} timeout")
        return Dossier(
            agent=agent,
            text=f"Findings from the {agent} agent.",
            citations=[f"https://example.com/{agent}-1", f"https://example.com/{agent}-2"],
        )


class FakeJudge:
    """Emits a valid report. `source_index` is overridable to test the citation backstop."""

    def __init__(self, source_index: int = 0) -> None:
        self.source_index = source_index
        self.prompts: list[str] = []

    async def judge(self, system: str, prompt: str) -> JudgeReport:
        self.prompts.append(prompt)
        return JudgeReport(
            verdict="A plausible but crowded idea with a narrow wedge available.",
            subscores=Subscores(
                market_size=80,
                novelty=60,
                competitive_headroom=40,
                feasibility=70,
                timing=50,
            ),
            competitors=[
                Competitor(
                    name="Example Corp",
                    domain="example.com",
                    what_they_do="Does roughly this, for a different segment.",
                    funding_stage="series-a",
                    sources=[self.source_index],
                )
            ],
            risks=[Risk(text="The incumbent could ship this as a feature.", sources=[])],
            differentiation=[
                DifferentiationAngle(text="Target the underserved low end.", sources=[])
            ],
        )
