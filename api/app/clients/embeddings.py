"""OpenAI embedding client, batched.

`langchain-openai` rather than the raw `openai` SDK for the same reason the
other providers are LangChain wrappers: free LangSmith spans, which was a day-1
decision. `OpenAIEmbeddings.aembed_documents` batches internally, so one
`embed()` call per run (idea + entities + chunks, ~10 texts) is a single API
request.
"""

from typing import Protocol

from app.config import get_settings

_settings = get_settings()


class EmbeddingClient(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class OpenAIEmbedder:
    def __init__(self, model: str | None = None) -> None:
        from langchain_openai import OpenAIEmbeddings

        self._model = OpenAIEmbeddings(
            model=model or _settings.embedding_model,
            api_key=_settings.openai_api_key,
        )

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return await self._model.aembed_documents(texts)
