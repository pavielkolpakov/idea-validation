import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from app.auth import set_verifier
from app.clients import build_clients, build_embedder, build_precheck, build_verifier
from app.config import get_settings
from app.graph.build import build_graph
from app.guardrails import set_precheck
from app.routers import auth, corpus, reports
from app.runner import set_embedder, set_graph

logging.basicConfig(level=logging.INFO)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # search_path pins the checkpointer's tables to their own schema, out of
    # `public` where Alembic autogenerate would propose dropping them.
    pool = AsyncConnectionPool(
        conninfo=settings.psycopg_dsn,
        max_size=settings.max_concurrent_runs + 2,
        open=False,
        kwargs={
            "autocommit": True,
            "prepare_threshold": 0,
            "row_factory": dict_row,
            "options": f"-csearch_path={settings.checkpointer_schema},public",
        },
    )
    await pool.open()

    async with pool.connection() as conn:
        await conn.execute(f'CREATE SCHEMA IF NOT EXISTS "{settings.checkpointer_schema}"')

    checkpointer = AsyncPostgresSaver(pool)
    await checkpointer.setup()  # idempotent

    set_verifier(build_verifier())
    set_precheck(build_precheck())
    research_client, judge = build_clients()
    set_graph(build_graph(checkpointer, research_client, judge))
    # None when OPENAI_API_KEY is unset: ingest then writes NULL embeddings.
    set_embedder(build_embedder())
    app.state.pool = pool
    try:
        yield
    finally:
        await pool.close()


def create_app() -> FastAPI:
    app = FastAPI(title="IdeaCheck API", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth.router)
    app.include_router(reports.router)
    app.include_router(corpus.router)

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
