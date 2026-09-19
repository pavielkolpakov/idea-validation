# api/ — FastAPI backend

Accepts an idea, runs the LangGraph pipeline in a bounded background task, persists the result. **Python 3.14**, managed with `uv`.

## Files

| Path | Role |
|---|---|
| `app/main.py` | App factory, CORS, lifespan — builds the connection pool, checkpointer, and graph |
| `app/config.py` | `pydantic-settings`; reads `api/.env`. Exposes `psycopg_dsn` (the SQLAlchemy URL without the `+psycopg` prefix) |
| `app/db.py` | Async engine + `get_db` request dependency |
| `app/models.py` | All 6 tables. `EMBEDDING_DIM = 1536` |
| `app/schemas.py` | Request/response models; idea length bounds, `ReportBody`, the gate error models |
| `app/scripts/dump_openapi.py` | `make types` step 1 — writes `openapi.json` with no server and no DB |
| `openapi.json` | **Generated, committed.** The contract `web/lib/api.gen.ts` is built from |
| `app/auth.py` | Identity. `Authorization: Bearer` (verified) or `X-Anon-Id` → get-or-create `users` row |
| `app/quota.py` | Atomic per-run quota claim, refund on failure, in-memory per-IP cap |
| `app/guardrails.py` | Holds the injected pre-check client (set during lifespan) |
| `app/routers/auth.py` | `POST /auth/claim` — moves an anonymous visitor's reports onto their new account |
| `app/routers/reports.py` | `POST /reports` (202) + its gates, `GET /reports` (history), `GET /reports/{public_slug}`, slug generation |
| `app/routers/corpus.py` | `GET /corpus/stats` — row/embedding counts; the only read window into the write-only corpus |
| `app/runner.py` | Semaphore-bounded background execution, status transitions, graph streaming, corpus ingest |
| `app/corpus.py` | Ingest: domain normalization, entity upsert (`ON CONFLICT`), one batched embedding call per run |
| `app/clients/` | Perplexity + Anthropic + OpenAI-embedding + token-verifier + pre-check clients behind protocols, plus the fakes the default suite runs on |
| `app/scripts/` | `python -m app.scripts.backfill` — one-shot backfill for pre-ingest reports |
| `app/graph/` | The LangGraph pipeline — see `app/graph/CLAUDE.md` |
| `alembic/` | Migrations. `env.py` carries the `include_object` hook |
| `tests/` | Integration tests against a real Postgres. Real DB, fake model providers |

## Conventions

- **Async everywhere.** SQLAlchemy 2.0 async on psycopg3, matching the checkpointer's driver. No lazy relationship loading — use explicit `selectinload`/`joinedload`.
- **`sqlalchemy[asyncio]`**, not plain `sqlalchemy` — the extra pulls `greenlet`, without which async connect fails at runtime.
- **Short-lived sessions in background work.** `runner._patch` opens a session per write rather than holding one across a 90s run; otherwise `max_concurrent_runs` runs exhaust the pool.
- **Nothing may escape into `BackgroundTasks`** — an exception there vanishes silently. `run_report` catches everything and records `status="failed"` with the error text.
- **Model providers are injected, not imported.** `build_graph` takes a `ResearchClient` and a `JudgeClient`; `app/clients/build_clients()` constructs the real ones and is the single seam tests monkeypatch. Adding a provider means adding a protocol here, not reaching for it inside a node.
- **So is identity.** `build_verifier()` and `build_precheck()` follow the same pattern. There is deliberately **no `DEV_AUTH` bypass**: an env var that disables auth is one misconfigured variable from an open API, and the failure is silent because everything keeps working. The fake verifier gives tests the same ergonomics with no bypass in shipped code.
- **An anonymous visitor is an ordinary `users` row** (`external_id = "anon:<uuid>"`), not a special case. That is why ownership, quota, history and the claim all work with no schema change — don't add a nullable-user branch.
- **The quota check and increment are one statement.** `quota.consume` is an `INSERT ... ON CONFLICT DO UPDATE ... WHERE count < limit RETURNING count`; over-quota is the *absence* of a returned row. A `SELECT` then `UPDATE` races a double-clicked submit, and losing that race costs a real Opus call. It deliberately **does not commit** — the caller holds the transaction through the insert so the row lock serializes concurrent claims too.
- **`quota.has_budget` is advisory, `quota.consume` is the gate.** The read exists only to turn an exhausted caller away before the *paid* pre-check runs; a race there costs one extra Haiku call, never a free report.
- **Corpus writes are best-effort and always last.** `runner._ingest` runs after the report row is committed and swallows its own errors: a corpus failure must never cost the user their report. Inside ingest, a missing/failed embedder degrades to NULL embeddings with the rows still written — the vector columns are nullable for exactly this reason. `make backfill` repairs ideas, chunks, and domain-keyed entities; a domainless entity has no key to repair on and stays NULL until similarity merge lands.
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

**Every request needs credentials.** The `auth` fixture mints a *unique* signed-in identity per test, because the test database is session-scoped and a shared user would carry one test's quota consumption into the next. The `client` fixture also gives each test its own client IP for the same reason.

**Real Postgres, fake model providers.** The "no mocks" convention was about the database, where Phase 1's risk lived; it still holds. Paid third-party HTTP is a different category — `conftest` monkeypatches `app.main.build_clients` to return `FakeResearchClient` / `FakeJudge`. That is also the only way to reach the behaviours that matter most: one researcher down, all four down, a judge citing a source that doesn't exist.

**`make test-live`** (`-m live`) runs the same pipeline against the real APIs. It costs money and is deselected by default. It exists to catch the fakes lying — specifically `extract_citations`, whose shape is currently an assumption. Run it before shipping.

## Gotchas (Phase 2)

- **`.env` is not the process environment.** pydantic-settings parses `api/.env` into the `Settings` object and stops; nothing lands in `os.environ`. Any library that reads `os.environ` directly sees an empty environment. `app/config.py::load_env_file` exports the file at import time to fix this — **real env vars still win**, so conftest's `DATABASE_URL` and any explicit `export` are never clobbered. This trap bit twice before being fixed: LangSmith tracing was silently off with every key correctly set, and the live test suite skipped itself while checking `os.environ` for keys that only existed in the file. If you add a setting that a third-party SDK reads from the environment, it must go through here.
- **The `perplexityai` SDK breaks LangSmith serialization.** `APIPublicSearchResult` ships with `__pydantic_complete__ = False` and a `MockValSer`, so LangSmith's `on_llm_end` raises while serializing it — and langchain-core swallows that into a log warning. Symptom: tracing appears enabled but every `ChatPerplexity` span sits at `status=pending` with no outputs, while `ChatAnthropic` traces fine. `repair_search_result_schema()` in `app/clients/perplexity.py` forces `model_rebuild`; it runs when the client is constructed. Remove it only after confirming upstream ships a built schema.
- **`search_results` items are SDK objects, not dicts.** Gating on `isinstance(r, dict)` silently matches nothing. `extract_citations` accepts both shapes; the flat `citations` list is the fallback.
- **`ASGITransport` awaits `BackgroundTasks` inside the POST**, so a report is already finished when the response returns. Tests that need to observe intermediate `step` values must poll concurrently with the request, not after it.
- **A LangGraph `RetryPolicy` on a research node would be dead config**, because those nodes swallow their own exceptions and never raise. Retry lives inside the node. See `app/graph/CLAUDE.md`.
- **`PERPLEXITY_CONCURRENCY` is not `MAX_CONCURRENT_RUNS`.** One run makes four Sonar calls, so 5 concurrent runs would mean 20 concurrent vendor requests. They are separate settings on purpose; don't collapse them.

## Gotchas (Phase 4)

- **`ReportBody` is not `JudgeReport`, and the duplication is deliberate.** `JudgeReport` is a *generation* contract — strict, so a bad judge output fails the run. `ReportBody` is a *serialization* contract over rows already in the database. Reusing the strict model as a response type turns any row written under older rules (a pre-rename `competitive_intensity`, a report with zero risks) into a 500 on `GET`: the user's paid-for report becomes unservable because of a rule that exists to police the LLM. `tests/test_api_contract.py` asserts the field sets stay in step so the copies can't drift.
- **`status` is a `Literal`, not `str`**, so the generated client gets an exhaustive union. It must stay equal to `models.REPORT_STATUSES` (which the DB `CHECK` enforces) — there's a test for that.
- **The gate responses are declared on the route** (`SUBMISSION_GATES`) and their bodies are built from the same Pydantic models that document them, so the documented shape and the real one cannot drift. The frontend branches on `reason` to tell "sign in" from "out of runs" from "you already ran this".
- **After touching `schemas.py` or a route, run `make types`** and commit `api/openapi.json` + `web/lib/api.gen.ts`. Vercel's build cannot reach the API to generate them.

- **`POST /reports` gate order is load-bearing**: per-IP cap (in-memory) → `has_budget` advisory read → pre-check (paid Haiku call) → advisory lock → duplicate → `consume` → insert → commit. Two constraints pin it: the *free* checks must precede the paid one, or an exhausted signed-in account can spend indefinitely by retrying (they are exempt from the IP cap); and the *authoritative* claim must come after the duplicate check, or rejected submissions burn credits.
- **The duplicate check and the insert are one critical section.** `quota.lock_submission` takes a `pg_advisory_xact_lock` keyed on `(user_id, idea)`, held until commit. Without it two concurrent identical submits both read "no duplicate", both consume a credit, and both launch a full research run — verified, and it is exactly what a double-clicked button does.
- **The refund takes the charged identity as an argument, not the report's owner.** `POST /auth/claim` rewrites `reports.user_id` while a run is in flight, so resolving the owner at failure time credits the account that just claimed the report and leaves the anonymous visitor who paid permanently out of pocket. `run_report` carries `charged_user_id`/`charged_period` for this reason.
- **`usage_counters.period` is `String(7)`.** Anonymous users are counted under the sentinel `'anon'` instead of `YYYY-MM`, because their id lives in `localStorage` and a monthly period hands out a fresh free run at every month boundary. A *daily* cap would not fit this column without a migration.
- **The per-IP cap reads `request.client.host`, not `X-Forwarded-For`.** uvicorn's `--proxy-headers` already rewrites `request.client` using the trusted-proxy list; hand-parsing the header means trusting a client-controlled value, and an attacker spoofing a fresh first hop per request defeats the cap entirely. **In production that flag is load-bearing** — without it every visitor shares one bucket and the third one gets a 429.
- **The IP limiter is an in-memory dict and resets on deploy.** That is the accepted trade: it is a speed bump in front of a wall (the second run needs an account), and one replica makes a shared store unnecessary.
- **A failed run refunds its credit.** Research is fail-soft, so `status="failed"` almost always means our bug — charging for it is the worst support conversation available. The refund is best-effort and must never replace the original error.
- **Duplicate detection is per user, never global.** Global dedupe would serve the first founder's report to the second and destroy the "N people pitched this" signal `ideas` exists for. `force: true` is the deliberate re-run escape hatch — `tests/test_corpus.py` depends on it.
- **The `md5(ideas.text)` index is declared in `models.py` as well as migration 0002.** Without the model-side `Index(...)`, `--autogenerate` proposes dropping it — the same trap as the checkpointer tables. Note `Idea` has a column named `text`, so the helper is imported as `sql_text`.

## Gotchas (Phase 3)

- **Entity upserts dedupe within the batch before `ON CONFLICT`.** Postgres cannot touch the same row twice in one `INSERT ... ON CONFLICT` statement, and the judge can name the same company in two dossiers — without the pre-dedupe in `upsert_entities`, that run fails with `CardinalityViolation`. Domain-less competitors are plain inserts (multiple NULLs are legal under the unique constraint).
- **The `OPENAI_API_KEY` is optional by design.** `build_embedder()` returns `None` and warns rather than raising like `build_clients` — the app is fully useful without embeddings, and the corpus invariant is best-effort. The tell is `GET /corpus/stats` showing `embedded < total`.
- **The backfill embeds every competitor on every pass, on purpose.** Skipping the ones whose entity already has a vector looks like free savings, and was tried: the upsert overwrites `description` on each sighting while coalescing the embedding, so a skipped pass leaves the previous description's vector under this pass's text. The spend is cents on a one-shot script; correctness is not.
- **A wrong-dimension model is not an embedding *failure*.** `text-embedding-3-large` returns 3072 dims against 1536-wide columns — the API call succeeds, so it cannot be caught as an exception; unguarded it surfaces at `commit()` and rolls back every row the run was writing. `OpenAIEmbedder` pins `dimensions=EMBEDDING_DIM`, and `corpus._embed` checks the returned length and degrades to NULL. Do not remove either: the client-side pin is prevention, the `_embed` check is what keeps the invariant true for a model that ignores it.
- **The test DB is session-scoped; corpus rows accumulate across tests.** Corpus tests use a unique judge domain each (`FakeJudge(domain=...)`) and the stats test asserts before/after deltas, never absolutes.
