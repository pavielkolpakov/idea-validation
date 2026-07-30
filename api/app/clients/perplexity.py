"""Perplexity Sonar research client.

Returns cited prose, not structured data: the judge is the structuring step
(see PLAN.md — entities are read off the judge's competitor table, so a second
extraction here would just create a second list that can disagree with it).
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.config import get_settings

log = logging.getLogger(__name__)
_settings = get_settings()


@dataclass
class Dossier:
    """One research agent's findings.

    Field-for-field the shape of a `research_chunks` row, so ingest is a loop
    with no transformation.
    """

    agent: str
    text: str
    citations: list[str] = field(default_factory=list)
    error: str | None = None

    @property
    def is_empty(self) -> bool:
        return not self.text.strip()


class ResearchClient(Protocol):
    async def research(self, agent: str, prompt: str) -> Dossier: ...


def extract_citations(message: Any) -> list[str]:
    """Pull source URLs out of a ChatPerplexity response.

    Verified against a live `sonar-pro` response (langchain-perplexity 1.4.0):

        response_metadata -> {"model_name", "search_context_size"}   # no citations
        additional_kwargs -> {"citations", "search_results"}         # both present

    So citations arrive on `additional_kwargs`, **not** `response_metadata` —
    `response_metadata` is checked first only as a cheap hedge against the
    wrapper relocating them. `search_results` is the richer form (dicts with
    url/title); `citations` is a flat list of the same URLs.

    This is the one payload whose exact shape the product depends on: it becomes
    `research_chunks.citations` and every citation index in the report. The
    `@pytest.mark.live` suite is what keeps it honest — treat a failure there as
    the shape having moved, not as a flaky test.
    """
    meta = getattr(message, "response_metadata", None) or {}
    extra = getattr(message, "additional_kwargs", None) or {}

    for source in (meta, extra):
        results = source.get("search_results")
        if isinstance(results, list) and results:
            # Items are `APIPublicSearchResult` SDK objects, NOT dicts — an
            # `isinstance(r, dict)` gate here silently matches nothing and leaves
            # the whole branch dead, so accept both shapes.
            urls = [_result_url(r) for r in results]
            urls = [u for u in urls if u]
            if urls:
                return urls
        citations = source.get("citations")
        if isinstance(citations, list) and citations:
            return [c for c in citations if isinstance(c, str)]
    return []


def _result_url(result: Any) -> str | None:
    if isinstance(result, dict):
        url = result.get("url")
    else:
        url = getattr(result, "url", None)
    return url if isinstance(url, str) and url else None


def repair_search_result_schema() -> bool:
    """Force the `perplexityai` SDK's search-result model to build its schema.

    The SDK ships `APIPublicSearchResult` with `__pydantic_complete__ = False`
    and a `MockValSer` placeholder serializer. Nothing in the request path cares
    — but LangSmith's `on_llm_end` tries to serialize it, raises
    `TypeError: 'MockValSer' object is not an instance of 'SchemaSerializer'`,
    and langchain-core swallows that into a log warning. The visible symptom is
    tracing that looks enabled while every ChatPerplexity span sits at
    `status=pending` with no outputs, forever.

    `model_rebuild(force=True)` completes the schema. Returns whether the model
    is usable afterwards; failure is non-fatal, since this only affects tracing.
    """
    try:
        from perplexity.types.shared.api_public_search_result import APIPublicSearchResult

        if not APIPublicSearchResult.__pydantic_complete__:
            APIPublicSearchResult.model_rebuild(force=True)
        return bool(APIPublicSearchResult.__pydantic_complete__)
    except Exception:  # noqa: BLE001 — upstream layout may change; tracing is not critical
        log.warning(
            "could not repair APIPublicSearchResult schema; Perplexity traces may be incomplete"
        )
        return False


class PerplexityClient:
    def __init__(self, model: str | None = None, concurrency: int | None = None) -> None:
        from langchain_perplexity import ChatPerplexity

        # Without this, LangSmith cannot serialize search results and every
        # ChatPerplexity span stays `pending` with no outputs.
        repair_search_result_schema()

        self._model = ChatPerplexity(
            model=model or _settings.sonar_model,
            pplx_api_key=_settings.perplexity_api_key,
            timeout=_settings.research_timeout_s,
        )
        self._semaphore = asyncio.Semaphore(concurrency or _settings.perplexity_concurrency)

    async def research(self, agent: str, prompt: str) -> Dossier:
        async with self._semaphore:
            message = await self._model.ainvoke(prompt)
        text = message.content if isinstance(message.content, str) else str(message.content)
        return Dossier(agent=agent, text=text, citations=extract_citations(message))
