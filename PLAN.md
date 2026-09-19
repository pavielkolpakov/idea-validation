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
- **Hosting provider** — **decided: Railway, single replica** (keeps `BackgroundTasks`, the semaphore and in-process streaming valid); not yet deployed.
- ~~**Auth provider**~~ — **Resolved (Phase 4): Clerk.** The discriminating requirement was that FastAPI verify identity by itself; Auth.js keeps the session in Next and would force either a proxy in front of the API (extra hop, breaks direct SSE) or hand-rolled JWT signing.
- Judge model tier (`claude-opus-5` vs `claude-sonnet-5`) — shipped as Opus via `JUDGE_MODEL`; A/B on the golden set.
- Research topology: fixed 4 sub-agents vs planner-driven `Send` fan-out — shipped fixed 4.

## MVP Features
- Idea input: freeform text (~1500 char cap), optional target-user field.
- Fan-out research: 4 sub-agents in parallel against Perplexity Sonar.
  1. **Direct competitors** — same problem, same approach.
  2. **Adjacent/incumbent** — larger players who could absorb this as a feature.
  3. **Market signals** — size, growth, recent funding, demand evidence.
  4. **Graveyard** — who tried this and died, and why.
- Judge pass: Claude reads all four dossiers + the idea, emits a structured report.
- Ingest: every run writes ideas / entities / research chunks with embeddings.
- Report page: score, subscores (novelty, market size, competitive **headroom**, timing, feasibility — all higher-is-better), competitor table, 3-5 risks, 3-5 differentiation angles, citations throughout.
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
                              END
```

The runner (not a graph node) then writes the report row, `dossiers_raw`, and the corpus chunks.

Key points:
- Four research nodes are separate graph nodes with static edges from START, not one node doing `asyncio.gather` — that's what lets the checkpointer resume a partial run, and what lets the planner-driven `Send` variant drop in later without restructuring.
- `dossiers` and `degraded_agents` need `Annotated[list, operator.add]`. Without the reducer, the last research node to finish overwrites the other three.
- **Amended in Phase 2: there is no `persist` node.** The original design had one, which contradicts the standing invariant that graph nodes never touch the database — the invariant is why nodes stay testable without a DB and why the stream is a clean SSE seam in Phase 4. The runner already did this work, so `persist` bought nothing.
  - *Known limitation this leaves open:* with persistence outside the graph, a process crash between the judge finishing and the runner's write leaves paid-for judge output sitting in the checkpoint with no path back into `reports`. Nothing triggers a resume today, so an in-graph `persist` would buy a guarantee we have no mechanism to collect on. Revisit if a resume endpoint is ever built.
- **Amended in Phase 2: retry is not a node-level `RetryPolicy`.** Research nodes swallow their own exceptions to keep the run alive, so they never raise — and a `RetryPolicy` on a node that never raises never fires. Retry sits inside the node, underneath the fail-soft catch.
- Corpus writes run last and swallow their own errors, so a corpus failure can never cost the user their report — the guarantee the original `persist → ingest` ordering was reaching for.
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

### Phase 2 — Pipeline ✅ complete
- [x] Perplexity client via `langchain-perplexity` (dedicated semaphore, timeout, citation extraction).
- [x] Four research node prompts; stub replaced with the real fan-out + reducers.
- [x] Judge prompt + Pydantic report schema via `langchain-anthropic` structured output.
- [x] Real failure handling (fail-soft research, all-empty floor) and aggregated `step` reporting.
- [x] `research_chunks` written per run with `embedding` NULL — corpus accumulation starts now.
- [x] Injected clients + fake-driven test suite; opt-in `make test-live` against the real APIs.

**Decisions and deviations, and why**
- **`langchain-perplexity` + `langchain-anthropic`**, not raw HTTP — free LangSmith spans, which was a day-1 decision.
- **Dossiers are flat prose + citations**, matching the `research_chunks` column shape exactly, so Phase 3 ingest is a loop with no transformation. Resolves the open chunking question below.
- **Research is fail-soft**; the judge raises only if all four dossiers are empty. `degraded_agents` in the report JSON keeps a thin report from being presented as a complete one. Consequence: `status="succeeded"` no longer means "all four researchers ran" — that fact lives in the JSON, because `status` is about the pipeline and `degraded_agents` is about the content.
- **Citations are integer indices into a code-built table, never URLs from the model.** An LLM asked for source URLs invents plausible ones, attached to factual claims about real companies. An out-of-range index fails validation instead of shipping.
- **The score is computed from subscores, not emitted by the judge** — see the weights in `app/graph/schema.py`. Makes the scale comparable across runs and lets Phase 4 re-score history from stored subscores at zero API spend.
- **`competitive_intensity` → `competitive_headroom`.** Every subscore must be higher-is-better or the weighted mean is silently wrong; a prompt sentence is not strong enough to hold that.
- **A separate `PERPLEXITY_CONCURRENCY`**, because `MAX_CONCURRENT_RUNS=5` now implies up to 20 concurrent Sonar requests. Report concurrency and vendor concurrency are different concerns.
- **Perplexity citation shape verified against a live `sonar-pro` response.** Citations arrive on `additional_kwargs` (both `citations` and `search_results`), *not* `response_metadata` — which carries only `model_name` and `search_context_size`. `make test-live` keeps this honest; treat a citation failure there as the contract having moved.
- **`search_context_size` comes back `low`** (the LangChain wrapper's default). Research depth is currently on its weakest setting — an untuned quality lever, not a decision.
- **LangSmith tracing verified end to end**: all 8 spans (4 research + judge chain/LLM/parser) close with outputs. Two bugs had to be fixed first, both silent: `.env` was never exported to `os.environ` (so tracing was simply off), and the `perplexityai` SDK's unbuilt `APIPublicSearchResult` schema broke LangSmith serialization, leaving every `ChatPerplexity` span `pending` forever. See `api/CLAUDE.md` → Gotchas.
- **Frontend untouched.** The report page remains Phase 4.

### Phase 3 — Corpus ingest ✅ complete
- [x] OpenAI embedding client (batched; one call per run via `langchain-openai`).
- [x] Ingest: ideas + entities (domain upsert) + chunks, all embedded.
- [x] Backfill script for reports produced before ingest landed (`make backfill`).
- [x] Corpus stats endpoint (`GET /corpus/stats`) — proves the asset is accumulating.

**Decisions and deviations, and why**
- **Ingest lives in the runner, not a graph node.** The Phase 2 amendment that dropped `persist` applies unchanged: nodes never touch the database, and the runner already owned `_write_chunks`. `app/corpus.py::ingest_run` is that function grown into full ingest — same best-effort swallow, same "after the report row commits" ordering.
- **`langchain-openai`**, matching the Phase 2 provider decision (free LangSmith spans). One batched `aembed_documents` call per run covers idea + entities + chunks (~10 texts).
- **A missing `OPENAI_API_KEY` is not fatal.** Unlike the research/judge keys, embeddings feed a corpus that is best-effort by invariant: `build_embedder()` returns `None` with a startup warning, and rows land with NULL embeddings (the columns are nullable for exactly this). An embedding *failure* mid-run degrades the same way — rows still written, vectors lost, backfillable.
- **Entity upsert dedupes within the batch first.** Postgres `ON CONFLICT` cannot touch the same row twice in one statement, and the judge can name a company in two dossiers. Domain-less competitors are plain inserts — no dedup story until embedding-similarity merge exists.
- **Repeat sightings refresh, never erase.** The upsert's `ON CONFLICT` clause bumps `seen_count`/`last_verified_at` and only overwrites `description`/`funding_stage`/`embedding` when the new value is non-NULL.
- **Backfill is a one-shot migration, not a cron job.** Re-running it against an already-ingested report inflates `seen_count`; that is documented in `app/scripts/backfill.py` rather than defended against with a marker column.
- **The embedding dimension is pinned in two places.** `OpenAIEmbedder` requests `dimensions=EMBEDDING_DIM` (the 3-series supports reduction, so `text-embedding-3-large` returns 1536), and `corpus._embed` checks the returned length. A wrong-dimension model is a *successful* API call, so it cannot arrive as an embedding failure — unguarded it surfaces at `commit()` and rolls back every row the run was writing, which is the one outcome the best-effort invariant exists to prevent.
- **Backfill re-embeds every competitor each pass.** Skipping already-embedded entities was tried and reverted: the upsert overwrites `description` on each sighting while coalescing the embedding, so a skipped pass strands the previous description's vector under this pass's text. Cents of spend against silent corpus corruption.

### Phase 4 — Product surface (in progress)

**Slice 1 — identity, quota, guardrails ✅ complete**
- [x] Auth provider decision: **Clerk**. `TokenVerifier` protocol + `ClerkVerifier` (JWKS, RS256); `X-Debug-User` removed.
- [x] Anonymous identity: client-minted uuid in `X-Anon-Id` → an ordinary `users` row (`external_id = "anon:<uuid>"`).
- [x] `POST /auth/claim` — moves an anonymous visitor's reports onto their new account.
- [x] Quota: atomic conditional upsert at submit, refund on `failed`, in-memory per-IP cap on anonymous runs.
- [x] Input guardrails: Haiku pre-check (spend) + `<idea>` fenced user-data blocks (injection).
- [x] Per-user duplicate detection with a `force` escape hatch; migration 0002 (`md5(ideas.text)` index).
- [x] `GET /reports` history, pulled forward from Slice 2 so the claim is verifiable through the public interface.

**Remaining**
- [ ] Tolerant `ReportBody` response model + OpenAPI type codegen (`web/lib/api.gen.ts`, committed).
- [ ] Report page (RSC shell + client view), share links, Clerk on the frontend.
- [ ] SSE progress streaming, replacing polling.
- [ ] Golden-set eval: ~15 ideas with known outcomes, judge-only over frozen dossiers.
- [ ] Hosting decision + deploy; lifespan sweep-and-resume for runs orphaned by a restart.

**Decisions and deviations, and why**
- **Anonymous visitors get one free run**, then a sign-in wall. They are stored as ordinary `users` rows, which is why ownership, quota, history and the claim all work with no schema change.
- **The anon id is a dedupe key, not a ceiling.** `X-Anon-Id` is forgeable by `curl`, so the real limit is a per-IP cap. It reads `request.client.host` rather than parsing `X-Forwarded-For` — uvicorn's `--proxy-headers` already applies the trusted-proxy list, and hand-parsing means trusting a client-controlled value that an attacker can vary per request. **That flag is load-bearing in production.**
- **Anonymous quota is counted under the sentinel period `'anon'`**, not `YYYY-MM`. The id lives in `localStorage` and survives the month rollover, so a monthly period would hand out a fresh free run every January. `usage_counters.period` is `String(7)`, which the sentinel fits — a *daily* cap would not.
- **The quota check and increment are one statement**, and the duplicate check shares its transaction under a `pg_advisory_xact_lock` keyed on `(user, idea)`. `SELECT`-then-`UPDATE` races a double-clicked submit; so does an unserialized duplicate check, which reproducibly launched two full research runs from one double-click before the lock landed.
- **Free gates precede paid ones.** A signed-in caller is exempt from the per-IP cap, so enforcing quota only *after* the Haiku pre-check let an exhausted account spend indefinitely by retrying. An advisory budget read now runs first; `consume` remains the authoritative gate.
- **The refund is addressed to whoever was charged**, carried into the run rather than resolved from the report at failure time — a claim can reassign the report mid-run.
- **A failed run refunds its credit.** Research is fail-soft, so `failed` almost always means our bug.
- **No `DEV_AUTH` bypass exists.** Tests inject a fake verifier through the same seam as the model clients. An env var that disables auth is one misconfiguration from an open API, and it fails silently because everything keeps working.
- **Duplicate detection is per user, never global.** Global dedupe would serve the first founder's report to the second and destroy the "N people pitched this" signal `ideas` exists for. `force: true` keeps the deliberate re-run available.
- **The `md5(ideas.text)` index is declared in `models.py` as well as the migration** — without it `--autogenerate` proposes dropping the index, the same trap the checkpointer tables have.
- **Prompt caching on the judge rubric was cut, on measurement.** `JUDGE_SYSTEM` is ~335 tokens against Claude Opus 5's 512-token minimum; even counting the structured-output tool schema, under 10% of a judge request is cacheable while four unique dossiers make up the rest. At this traffic the 5-minute TTL means writes (1.25×) with almost no reads — a surcharge, not a saving. Revisit as an eval-harness concern, where fixed dossiers are the reusable prefix.
- **Deploy is last, by choice.** The hedge is writing the Dockerfile/Railway config early and pointing the local app at a managed Postgres once, so pgvector, SSL and pool sizing are proven before Clerk and SSE are in the mix.

## Open Questions
- ~~Sonar tier: `sonar` vs `sonar-pro`.~~ **Resolved (Phase 2): `sonar-pro`**, config-driven via `SONAR_MODEL`. Developing against the cheap tier can't distinguish "the idea doesn't work" from "the research was underpowered"; downgrading later is a `.env` edit. Revisit per-node tiers once real outputs have been read.
- ~~Chunking strategy for `research_chunks`.~~ **Resolved (Phase 2): whole sub-agent answer as one row.** Matches the dossier shape, so no splitter and no transformation. Per-claim splitting stays available later, when retrieval quality can actually be measured.
- Judge model tier — defaulted to `claude-opus-5`; still wants the Phase 4 golden-set A/B against `claude-sonnet-5`. Config flip, no code change.
- When retrieval turns on: HNSW parameters, and how to stop the corpus echoing itself beyond the `source` column.
- Domainless entities have no dedup key, so they are re-inserted rather than repaired on every backfill pass and their embeddings stay NULL. Folds into the embedding-similarity merge question above — a name-based key was rejected as worse than the gap.
- ~~Idempotency on duplicate idea submissions.~~ **Resolved (Phase 4): per-user, 7-day window**, `409` with the existing slug and a `force` flag to re-run. Deliberately not global — see the Phase 4 notes.
- Score weights are a first guess (`SCORE_WEIGHTS`). Retune against the Phase 4 golden set; historical reports can be re-scored from stored subscores for free.
