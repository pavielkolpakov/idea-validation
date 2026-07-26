from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://ideacheck:ideacheck@localhost:5433/ideacheck"

    max_concurrent_runs: int = 5
    max_idea_chars: int = 1500

    cors_origins: str = "http://localhost:3000"

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
