import os
from functools import lru_cache
from pathlib import Path

from dotenv import dotenv_values
from pydantic_settings import BaseSettings, SettingsConfigDict

API_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = API_DIR / ".env"


def load_env_file(path: Path = ENV_FILE) -> None:
    """Export `.env` into `os.environ`.

    pydantic-settings reads `.env` into the `Settings` object and stops there,
    which is invisible to anything that reads `os.environ` directly. LangSmith's
    tracer does exactly that: with `LANGSMITH_TRACING=true` sitting in `.env` but
    not in the environment, tracing silently never happens — no error, no warning,
    just no traces. Same trap caught the live test suite, which was checking
    `os.environ` for API keys that only ever existed in the file.

    Real environment variables win, so an explicit `export` (or conftest setting
    DATABASE_URL before app import) is never clobbered by the file.
    """
    if not path.is_file():
        return
    for key, value in dotenv_values(path).items():
        if value is not None and key not in os.environ:
            os.environ[key] = value


# Must run before anything imports langchain/langsmith, which read the
# environment when their tracer is first constructed.
load_env_file()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://ideacheck:ideacheck@localhost:5433/ideacheck"

    max_concurrent_runs: int = 5
    max_idea_chars: int = 1500

    cors_origins: str = "http://localhost:3000"

    perplexity_api_key: str = ""
    anthropic_api_key: str = ""

    # Deliberately NOT fail-fast like the two keys above: embeddings feed the
    # write-only corpus, and corpus writes are best-effort by invariant. A
    # missing key means rows land with NULL embeddings (the columns are nullable
    # for exactly this) and a warning at startup — never a dead app.
    openai_api_key: str = ""
    embedding_model: str = "text-embedding-3-small"

    # Free quota. The anonymous run is marketing spend; the per-account limit
    # is the real ceiling.
    anon_free_runs: int = 1
    monthly_free_runs: int = 5
    # The actual ceiling on anonymous traffic: the anon id is forgeable.
    anon_runs_per_ip: int = 3
    anon_ip_window_s: float = 86400.0

    # Identity. Fatal when unset (see clients.build_verifier) — unlike the
    # embedding key, nothing works without it.
    clerk_jwks_url: str = ""
    clerk_issuer: str = ""

    sonar_model: str = "sonar-pro"
    judge_model: str = "claude-opus-5"
    # Cheap gate in front of the expensive pipeline.
    precheck_model: str = "claude-haiku-4-5"

    # Deliberately not max_concurrent_runs: that bounds *reports* in flight, a
    # UX/pool concern. This bounds concurrent requests to Perplexity, a vendor
    # rate-limit concern. One run makes four calls, so they are not the same
    # number and must not drift into each other by accident.
    perplexity_concurrency: int = 8
    research_timeout_s: float = 90.0

    # Retry happens inside the research node, not as a LangGraph RetryPolicy:
    # the node swallows its exceptions to keep the run alive, so it never raises,
    # and a RetryPolicy on a node that never raises never fires.
    research_retry_attempts: int = 3
    research_retry_base_delay_s: float = 1.0

    # Checkpointer tables live here, deliberately outside `public` so Alembic
    # autogenerate can never propose dropping them. See alembic/env.py.
    checkpointer_schema: str = "langgraph"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def psycopg_dsn(self) -> str:
        """Raw libpq DSN for psycopg/langgraph, which don't understand the SQLAlchemy prefix."""
        return self.database_url.replace("postgresql+psycopg://", "postgresql://")


@lru_cache
def get_settings() -> Settings:
    return Settings()
