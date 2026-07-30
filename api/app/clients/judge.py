"""Claude judge: reads the four dossiers, emits a structured report.

Model comes from settings rather than a literal so the tier is a `.env` edit and
the Phase 4 A/B is a config flip, not a code change.
"""

from typing import Protocol

from app.config import get_settings
from app.graph.schema import JudgeReport

_settings = get_settings()


class JudgeClient(Protocol):
    async def judge(self, system: str, prompt: str) -> JudgeReport: ...


class AnthropicJudge:
    def __init__(self, model: str | None = None) -> None:
        from langchain_anthropic import ChatAnthropic

        self._model = ChatAnthropic(
            model=model or _settings.judge_model,
            api_key=_settings.anthropic_api_key,
            max_tokens=16000,
        ).with_structured_output(JudgeReport)

    async def judge(self, system: str, prompt: str) -> JudgeReport:
        return await self._model.ainvoke(
            [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
        )
