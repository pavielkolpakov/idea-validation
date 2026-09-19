"""Integration test setup.

Everything risky in Phase 1 is an interaction — async pool, Alembic, pgvector,
background tasks — so tests run against a real Postgres, not mocks. The fixture
creates a separate database and runs `alembic upgrade head` against it, which
means the migrations themselves are exercised on every test run.
"""

import os
from collections.abc import AsyncIterator
from pathlib import Path

import psycopg
import pytest

API_DIR = Path(__file__).resolve().parent.parent


def _unique_ip() -> str:
    from uuid import uuid4

    n = uuid4().int
    return f"10.{n % 251}.{(n >> 8) % 251}.{(n >> 16) % 251}"


ADMIN_DSN = "postgresql://ideacheck:ideacheck@localhost:5433/postgres"
TEST_DB = "ideacheck_test"
TEST_SQLALCHEMY_URL = f"postgresql+psycopg://ideacheck:ideacheck@localhost:5433/{TEST_DB}"

# Must be set before any app module reads settings.
os.environ["DATABASE_URL"] = TEST_SQLALCHEMY_URL
# Retry behaviour is under test; the backoff sleeps are not.
os.environ["RESEARCH_RETRY_BASE_DELAY_S"] = "0"


@pytest.fixture(scope="session", autouse=True)
def test_database() -> None:
    with psycopg.connect(ADMIN_DSN, autocommit=True) as conn:
        conn.execute(
            f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            f"WHERE datname = '{TEST_DB}' AND pid <> pg_backend_pid()"
        )
        conn.execute(f'DROP DATABASE IF EXISTS "{TEST_DB}"')
        conn.execute(f'CREATE DATABASE "{TEST_DB}"')

    from alembic.config import Config

    from alembic import command

    cfg = Config(str(API_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", TEST_SQLALCHEMY_URL)
    command.upgrade(cfg, "head")


@pytest.fixture
def research_client():
    from app.clients.fakes import FakeResearchClient

    return FakeResearchClient()


@pytest.fixture
def judge():
    from app.clients.fakes import FakeJudge

    return FakeJudge()


@pytest.fixture
def embedder():
    from app.clients.fakes import FakeEmbeddingClient

    return FakeEmbeddingClient()


@pytest.fixture
def verifier():
    from app.clients.fakes import FakeVerifier

    return FakeVerifier()


@pytest.fixture
def precheck():
    from app.clients.fakes import FakePrecheck

    return FakePrecheck()


@pytest.fixture
def auth(verifier) -> dict[str, str]:
    """Headers for a signed-in caller, unique per test.

    Unique on purpose: the test database is session-scoped, so a shared identity
    would carry one test's quota consumption into the next.
    """
    from uuid import uuid4

    token = f"tok-{uuid4()}"
    verifier.tokens[token] = f"user_{uuid4().hex[:12]}"
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def client(
    test_database, research_client, judge, embedder, verifier, precheck, monkeypatch
) -> AsyncIterator:
    import httpx

    from app.main import app

    # The real clients construct eagerly at startup and need live API keys, so
    # the default suite swaps them here. Postgres stays real — that convention
    # was about the database, where the risk actually lives.
    monkeypatch.setattr("app.main.build_clients", lambda: (research_client, judge))
    # Same seam for the embedder; set `embedder.fail = True` to exercise the
    # NULL-embedding path.
    monkeypatch.setattr("app.main.build_embedder", lambda: embedder)
    # Same seam for identity: the real verifier needs a reachable Clerk JWKS.
    monkeypatch.setattr("app.main.build_verifier", lambda: verifier)
    monkeypatch.setattr("app.main.build_precheck", lambda: precheck)

    # ASGITransport does not run lifespan events, and lifespan is where the
    # checkpointer and graph are built — so drive it explicitly.
    async with app.router.lifespan_context(app):
        # Unique per test: the per-IP anonymous cap is global state, and
        # ASGITransport otherwise reports the same client address everywhere.
        transport = httpx.ASGITransport(app=app, client=(_unique_ip(), 12345))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            yield c
