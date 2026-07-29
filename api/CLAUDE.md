# api/ — FastAPI backend

Accepts an idea, runs the LangGraph pipeline in a bounded background task, persists the result. **Python 3.14**, managed with `uv`.

## Files

| Path | Role |
|---|---|
| `app/main.py` | App factory, CORS, lifespan — builds the connection pool, checkpointer, and graph |
| `app/config.py` | `pydantic-settings`; reads `api/.env`. Exposes `psycopg_dsn` (the SQLAlchemy URL without the `+psycopg` prefix) |
| `app/db.py` | Async engine + `get_db` request dependency |
| `app/models.py` | All 6 tables. `EMBEDDING_DIM = 1536` |
| `app/schemas.py` | Request/response models; idea length bounds live here |
| `app/auth.py` | **Placeholder.** `X-Debug-User` header → get-or-create `users` row. Phase 4 replaces this file wholesale |
| `app/routers/reports.py` | `POST /reports` (202), `GET /reports/{public_slug}`, slug generation |
| `app/runner.py` | Semaphore-bounded background execution, status transitions, graph streaming |
| `app/graph/` | The LangGraph pipeline — see `app/graph/CLAUDE.md` |
| `alembic/` | Migrations. `env.py` carries the `include_object` hook |
| `tests/` | Integration tests against a real Postgres; no mocks |

## Conventions

- **Async everywhere.** SQLAlchemy 2.0 async on psycopg3, matching the checkpointer's driver. No lazy relationship loading — use explicit `selectinload`/`joinedload`.
- **`sqlalchemy[asyncio]`**, not plain `sqlalchemy` — the extra pulls `greenlet`, without which async connect fails at runtime.
- **Short-lived sessions in background work.** `runner._patch` opens a session per write rather than holding one across a 90s run; otherwise `max_concurrent_runs` runs exhaust the pool.
- **Nothing may escape into `BackgroundTasks`** — an exception there vanishes silently. `run_report` catches everything and records `status="failed"` with the error text.
- Line length 100, ruff with `E,F,I,UP,B`.

## Gotchas

- **Alembic autogenerate and the checkpointer.** LangGraph owns `checkpoints`, `checkpoint_writes`, `checkpoint_blobs`, `checkpoint_migrations` in the `langgraph` schema. `alembic/env.py`'s `include_object` hook filters out non-`public` schemas — **without it, autogenerate emits `DROP TABLE checkpoints`.** After changing migrations, verify with `alembic revision --autogenerate` and confirm the body is `pass`.
- The schema is pinned by the connection's `search_path` in `main.py`, because `AsyncPostgresSaver` has no `schema` parameter.
- **Migration and models must agree on nullability.** `Mapped[datetime]` (non-optional) means `nullable=False`; a mismatch shows up as autogenerate drift.
- **Python 3.14 evaluates annotations lazily (PEP 649).** SQLAlchemy's declarative mapper resolves `Mapped[...]` by introspecting annotations, so this path is version-sensitive. It is verified working on the pinned versions — if you bump SQLAlchemy or Python, re-run the suite rather than assuming, since a failure surfaces at mapper configuration, not import.
- Vector columns exist but are **nullable and unindexed**. Embeddings arrive in Phase 3; HNSW indexes only when retrieval is switched on.
- `status` is `text` + `CHECK`, not a Postgres enum — adding a value must not require `ALTER TYPE`. Code branches on `status`; `step` is free text for the UI and can change freely.

## Testing

`make test` creates and migrates `ideacheck_test`, so **migrations are exercised on every run**. Tests drive the app through `httpx.ASGITransport` and explicitly enter `app.router.lifespan_context` — ASGITransport does not run lifespan events, and lifespan is where the graph is built.
