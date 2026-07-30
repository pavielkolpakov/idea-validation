"""External model providers, behind protocols.

The protocols exist so `build_graph` can be handed fakes in tests. The DB stays
real in every test (Phase 1's convention); paid third-party HTTP is a different
category and is substitutable here.

`build_clients` is the seam tests monkeypatch — the real clients construct
eagerly at app startup and would need live API keys otherwise.
"""

from app.clients.judge import AnthropicJudge, JudgeClient
from app.clients.perplexity import Dossier, PerplexityClient, ResearchClient

__all__ = [
    "AnthropicJudge",
    "Dossier",
    "JudgeClient",
    "PerplexityClient",
    "ResearchClient",
    "build_clients",
]


def build_clients() -> tuple[ResearchClient, JudgeClient]:
    """Construct the real providers, failing fast if they can't work.

    Phase 2 made the app unbootable without provider keys, which is correct — it
    can do nothing useful without them. Without this check the failure is a
    vendor SDK exception raised from inside a constructor, which says nothing
    about this project or where the key is supposed to go.
    """
    from app.config import get_settings

    settings = get_settings()
    missing = [
        name
        for name, value in (
            ("PERPLEXITY_API_KEY", settings.perplexity_api_key),
            ("ANTHROPIC_API_KEY", settings.anthropic_api_key),
        )
        if not value.strip()
    ]
    if missing:
        raise RuntimeError(
            f"missing required provider key(s): {', '.join(missing)}. "
            f"Set them in api/.env (see .env.example). Tests do not need them — "
            f"the default suite runs on fakes via `make test`."
        )

    return PerplexityClient(), AnthropicJudge()
