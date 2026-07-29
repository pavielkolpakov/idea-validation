# IdeaCheck

## Overview
A public web app where anyone pastes a startup/product idea and gets back a structured validation report: who already does this, what the market signals say, what the main risks are, and a 0-100 score with a written verdict. Research is done by parallel sub-agents hitting the Perplexity Sonar API; a Claude judge synthesizes their findings into the scored report.

Every run also writes into our own Postgres + pgvector corpus — ideas, discovered companies, and raw research chunks, all embedded. V1 does not read from that corpus; it exists so that by the time we turn retrieval on, there is something worth retrieving.

Target user: solo founders and indie hackers deciding whether to build.

## Decisions Made

### Product & architecture
| Decision | Choice | Rationale |
|---|---|---|
| Delivery | Public web app | — |
| Output | Structured report + 0-100 score | — |
| Stack shape | Next.js frontend + Python backend | Python for the agent/embedding ecosystem |
| Research API | Perplexity Sonar | Synthesis + citations built in |
| Orchestration | LangGraph | Fan-out/fan-in now; refine loops, follow-up chat, dynamic planners are additive later |
| Embeddings | OpenAI `text-embedding-3-small` (1536-dim) | Cheap, ubiquitous; Anthropic has no embeddings API |
| Corpus | Ingest all three tiers from day 1, **no RAG in V1** | Writing is cheap now; backfilling embeddings later is not |
| Execution | FastAPI `BackgroundTasks` + LangGraph Postgres checkpointer | No new vendor; checkpointer makes a crashed run resumable instead of re-burning 4 Perplexity calls |
| Execution upgrade path | Postgres-as-queue (procrastinate/pgqueuer) | Same DB, no Redis. The semaphore is the seam it replaces |
| Observability | LangSmith tracing from day 1 | Replay a misbehaving fan-out visually, without adopting the LangGraph Platform runtime |
| Python version | 3.14 | Full suite verified on 3.14 (incl. PEP 649 lazy annotations vs SQLAlchemy `Mapped[]`). Longer support runway than 3.12 and matches the dev machine's system Python. Not chosen for speed — the workload is IO-bound |
| TypeScript version | Stay on 5.x | TS 7.0.2 works for `tsc` but **typescript-eslint refuses it outright** and Next needs `experimental.useTypeScriptCli`. Revisit when typescript-eslint ships TS 7 support — that's the gating dependency |

### Implementation (settled in the Phase 1 grilling)
| Decision | Choice | Rationale |
|---|---|---|
| Auth | Deferred past Phase 1 | Provider choice leaks into the schema; nothing in Phases 1-3 needs a real user. `users.external_id` is provider-agnostic; dev uses an `X-Debug-User` header |
| Repo shape | Plain monorepo, no workspace tooling | `web/` and `api/` share no code. Types shared later via OpenAPI codegen, not a workspace |
| Local dev | Postgres in Docker (`pgvector/pgvector:pg17`), apps on host | Only Postgres has a nontrivial install. Native reload and debugging for both apps |
| DB layer | Async SQLAlchemy 2.0 on psycopg3 | One async stack shared with `AsyncPostgresSaver`. Needs explicit eager loading; Alembic stays sync |
| Primary keys | `bigint` identity + `public_slug` on reports | Small indexes (matters with 1536-dim vectors), no insert fragmentation, IDs never exposed |
| Vector schema | Columns in migration 1, **HNSW indexes deferred** | Indexes tax every insert; nothing reads them in V1. Tune `m`/`ef_construction` against real data later |
| Status model | `text` + `CHECK` (`queued`/`running`/`succeeded`/`failed`) + nullable `step`, `error` | Coarse status is what code branches on; `step` drives UI and evolves without migrations or drifting from the checkpointer |
| Phase 1 execution | Real `StateGraph` with one stub node | Validates BackgroundTasks + checkpointer + status transitions + polling at zero API spend. Phase 2 swaps the node body |
| Frontend in Phase 1 | One unstyled submit + poll page | Proves the contract from a browser, catches CORS on day one. Tailwind installed now, no other UI decisions |
| Testing | One integration test against a real test DB | Phase 1 risk is all interaction (async pool, Alembic, pgvector). Fixture runs `alembic upgrade head`, so migrations are tested every run |
| Checkpointer tables | Same DB, `langgraph` schema, excluded from Alembic autogenerate | Otherwise `--autogenerate` proposes `DROP TABLE checkpoints` and you lose run state |
| Concurrency | `asyncio.Semaphore`, default 5 | Bounded in-process runs; excess reports wait in `queued`. The seam the Postgres queue later replaces |

## Still Open
- **Hosting provider** — deferrable; local docker-compose unblocks Phases 1-3.
- **Auth provider** — decide in Phase 4 when org/social-login needs are known.
- Judge model tier (`claude-opus-5` vs `claude-sonnet-5`) — default Opus, A/B on the golden set.
- Research topology: fixed 4 sub-agents vs planner-driven `Send` fan-out — default fixed 4.

## MVP Features
- Idea input: freeform text (~1500 char cap), optional target-user field.
- Fan-out research: 4 sub-agents in parallel against Perplexity Sonar.
  1. **Direct competitors** — same problem, same approach.
  2. **Adjacent/incumbent** — larger players who could absorb this as a feature.
  3. **Market signals** — size, growth, recent funding, demand evidence.
  4. **Graveyard** — who tried this and died, and why.
- Judge pass: Claude reads all four dossiers + the idea, emits a structured report.
- Ingest: every run writes ideas / entities / research chunks with embeddings.
- Report page: score, subscores (novelty, market size, competitive intensity, timing, feasibility), competitor table, 3-5 risks, 3-5 differentiation angles, citations throughout.
- Accounts + history, shareable public link per report.
- Free quota per account.

## Out of Scope (v1)
- **Retrieval over our own corpus** (write-only in V1 — the deliberate deferral).
- Payments/subscriptions.
- Follow-up chat over the research.
- PDF export, team workspaces, non-English ideas.
- Idea refinement loop.

## Architecture

### Graph (LangGraph `StateGraph`)

```
                      ┌──────────────────────────┐
  START ──────────────┤  fan-out (static edges)  │
                      └──┬────┬────┬────┬────────┘
                         │    │    │    │
              competitors│    │    │    │graveyard
                    incumbents│    │market_signals
                         ▼    ▼    ▼    ▼
                    ┌──────────────────────┐
                    │ dossiers: Annotated  │   ← reducer: operator.add
                    │ [list, operator.add] │
                    └──────────┬───────────┘
                               ▼
                          ┌─────────┐
                          │  judge  │  Claude + structured output
                          └────┬────┘
                               ▼
                          ┌─────────┐
                          │ persist │  report row → status=succeeded
                          └────┬────┘
                               ▼
                          ┌─────────┐
                          │ ingest  │  embeddings → corpus (errors swallowed)
                          └────┬────┘
                              END
```

Key points:
- Four research nodes are separate graph nodes with static edges from START, not one node doing `asyncio.gather` — that's what lets the checkpointer resume a partial run, and what lets the planner-driven `Send` variant drop in later without restructuring.
- `dossiers` needs `Annotated[list, operator.add]`. Without the reducer, the last research node to finish overwrites the other three.
- Each research node gets a `RetryPolicy` — Perplexity timeouts are transient.
- `persist` runs before `ingest` so a corpus-write failure can never cost the user their report. `ingest` swallows its own errors and logs.
- `thread_id` = the report's ID. One thread per report; that's what makes a crashed run resumable.
- **Later (not V1):** a `retrieve_prior` node hangs off START alongside the research nodes, contributing a separately-labeled dossier so the judge can weigh our own prior findings against today's web results.

### Corpus (Postgres + pgvector)

| Table | Written per run | Embedded field | Notes |
|---|---|---|---|
| `ideas` | 1 row | idea text | Enables "N people pitched this", trend analysis |
| `entities` | N rows | name + description | **The asset.** Upsert keyed on normalized domain |
| `research_chunks` | ~4+ rows | chunk text | Raw sub-agent findings + their citations |

- Entities are read straight off the judge's structured competitor table — no separate extraction call.
- `entities` carries `first_seen_at`, `last_verified_at`, `seen_count`. Nothing reads these in V1, but they're what makes staleness handling possible when retrieval turns on.
- Domain normalization on write (strip scheme/www/path, lowercase). Embedding-similarity merge for near-duplicates is deferred — the domain key handles the common case.

## Data Model
- `users` — `id`, `external_id` (provider-agnostic, nullable in Phase 1), `email`, `created_at`.
- `reports` — `id`, `user_id`, `idea_id`, `status`, `step`, `error`, `dossiers_raw` (jsonb), `report` (jsonb), `score`, `public_slug` (unique), timestamps.
- `ideas` — `id`, `text`, `embedding vector(1536)` (nullable), `created_at`.
- `entities` — `id`, `name`, `domain` (unique), `description`, `funding_stage`, `embedding vector(1536)` (nullable), `first_seen_at`, `last_verified_at`, `seen_count`, `source`.
- `research_chunks` — `id`, `report_id`, `agent`, `text`, `citations` (jsonb), `embedding vector(1536)` (nullable), `source`.
- `usage_counters` — `user_id`, `period`, `count`.

`source` (`web` | `corpus`) exists from the first migration so that, once retrieval is on, corpus-derived claims can never be re-ingested as fresh findings — otherwise a wrong finding from report #10 gets retrieved into report #50, repeated by the judge, and re-ingested as corroborated. One column now, unfixable later.

## Implementation Phases

### Phase 1 — Foundation ✅ complete
- [x] Repo scaffold: `web/`, `api/`, root `docker-compose.yml`, `Makefile`, `.env.example`.
- [x] docker-compose: `pgvector/pgvector:pg17`, named volume, **host port 5433**.
- [x] `api/` via `uv`, **Python 3.14**. FastAPI + async SQLAlchemy + Alembic + LangGraph.
- [x] SQLAlchemy models for all six tables; bigint identity PKs, nullable `vector(1536)` columns, no HNSW indexes.
- [x] Alembic migration 1: `CREATE EXTENSION vector`, `CREATE SCHEMA langgraph`, all tables, `CHECK` on `reports.status`, unique on `public_slug` and `entities.domain`.
- [x] `alembic/env.py`: `include_object` hook excluding non-`public` schemas.
- [x] `AsyncPostgresSaver` pinned to the `langgraph` schema via `search_path`; `.setup()` on app startup.
- [x] Stub `StateGraph`: one node, sleeps ~3s, writes a canned report payload, updates `step`.
- [x] `POST /reports` → insert `queued` row → schedule background run → `202 {id, public_slug, status}`.
- [x] Background runner: semaphore-bounded, `queued → running → succeeded`, exceptions → `failed` + `error`.
- [x] `GET /reports/{public_slug}` → row as JSON.
- [x] `X-Debug-User` header shim resolving to a `users` row.
- [x] CORS for `localhost:3000`, verified in a real browser with zero console errors.
- [x] `web/`: Next.js 16 + TS + Tailwind; one page — textarea, submit, poll, raw JSON.
- [x] Integration test: fixture creates test DB + `alembic upgrade head`; POST → poll → assert `succeeded`. 5 tests passing.

**Deviations from spec, and why**
- **Host port 5433, not 5432.** A local Homebrew Postgres binds `127.0.0.1:5432` and silently shadows the container on `localhost`. Moving the container avoids touching a service used by other projects.
- **Six tables, not seven** — the plan miscounted; the data model always listed six.
- **`sqlalchemy[asyncio]` extra required.** Plain `sqlalchemy` doesn't pull `greenlet` on this platform, and async SQLAlchemy fails at connect time without it.
- **Checkpointer schema set via connection `search_path`**, since `AsyncPostgresSaver` exposes no `schema` parameter.
- Next 16 ships an `AGENTS.md` warning its conventions differ from older versions; its bundled docs were consulted before writing the page.

### Phase 2 — Pipeline
- [ ] Perplexity client (retry, timeout, citation extraction).
- [ ] Four research node prompts; replace the stub with the real fan-out + reducer.
- [ ] Judge prompt + Pydantic report schema, structured output.
- [ ] `persist` node; real failure handling and `step` reporting.

### Phase 3 — Corpus ingest
- [ ] OpenAI embedding client (batched).
- [ ] `ingest` node: ideas + entities (domain upsert) + chunks.
- [ ] Backfill script for reports produced before ingest landed.
- [ ] Corpus stats endpoint — proves the asset is accumulating.

### Phase 4 — Product surface
- [ ] Auth provider decision + integration; `X-Debug-User` removed.
- [ ] Hosting decision + deploy.
- [ ] SSE progress streaming, replacing polling.
- [ ] Report page, history, public share links; OpenAPI type codegen.
- [ ] Quota enforcement, input guardrails, prompt caching on the judge rubric.
- [ ] Golden-set eval: ~15 ideas with known outcomes, check score ordering is sane.

## Open Questions
- Sonar tier: `sonar` vs `sonar-pro`.
- Chunking strategy for `research_chunks`: whole sub-agent answer as one row, or split per claim? Per-claim is better for retrieval, more rows, needs a splitter.
- When retrieval turns on: HNSW parameters, and how to stop the corpus echoing itself beyond the `source` column.
- Idempotency on duplicate idea submissions — needs a content hash and a "you already ran this" UX.
