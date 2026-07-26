# IdeaCheck

## Overview
A public web app where anyone pastes a startup/product idea and gets back a structured validation report: who already does this, what the market signals say, what the main risks are, and a 0-100 score with a written verdict. Research is done by parallel sub-agents hitting the Perplexity Sonar API; a Claude judge synthesizes their findings into the scored report.

Every run also writes into our own Postgres + pgvector corpus — ideas, discovered companies, and raw research chunks, all embedded. V1 does not read from that corpus; it exists so that by the time we turn retrieval on, there is something worth retrieving.

Target user: solo founders and indie hackers deciding whether to build.

## Decisions Made
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
| Execution upgrade path | Postgres-as-queue (procrastinate/pgqueuer) | Same DB, no Redis. Node boundary designed so only the caller of `graph.ainvoke` changes |
| Observability | LangSmith tracing from day 1 | Replaying a misbehaving fan-out visually, without adopting the LangGraph Platform runtime |

## Still Open
- Hosting and auth provider — **deferrable**: local docker-compose unblocks Phases 1-3.
- Judge model tier (`claude-opus-5` vs `claude-sonnet-5`) — default to Opus, A/B on the golden set.
- Research topology: fixed 4 sub-agents vs planner-driven `Send` fan-out — default to fixed 4.

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
- **Retrieval over our own corpus** (write-only in V1 — this is the deliberate deferral).
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
                    ┌─────────────────────┐
                    │  dossiers: Annotated│   ← reducer: operator.add
                    │  [list, operator.add]│
                    └──────────┬──────────┘
                               ▼
                          ┌─────────┐
                          │  judge  │  Claude + structured output
                          └────┬────┘
                               ▼
                          ┌─────────┐
                          │ persist │  report row → status=done
                          └────┬────┘
                               ▼
                          ┌─────────┐
                          │ ingest  │  embeddings → corpus (errors swallowed)
                          └────┬────┘
                              END
```

Key points:
- Four research nodes are separate graph nodes with static edges from START, not one node doing `asyncio.gather` — that's what makes the checkpointer able to resume a partial run, and what lets the planner-driven `Send` variant drop in later without restructuring.
- `dossiers` needs `Annotated[list, operator.add]`. Without the reducer, the last research node to finish overwrites the other three.
- Each research node gets a `RetryPolicy` — Perplexity timeouts are transient.
- `persist` runs before `ingest` so a corpus-write failure can never cost the user their report. `ingest` swallows its own errors and logs.
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
- HNSW index on each embedding column, created in the initial migration so we're not reindexing a large table later.

## Data Model (sketch)
- `users` — mirrored from the auth provider.
- `reports` — `id`, `user_id`, `idea_id`, `status`, `dossiers_raw` (jsonb), `report` (jsonb), `score`, `public_slug`, timestamps.
- `ideas` — `id`, `text`, `embedding vector(1536)`, `created_at`.
- `entities` — `id`, `name`, `domain` (unique), `description`, `funding_stage`, `embedding vector(1536)`, `first_seen_at`, `last_verified_at`, `seen_count`, `source`.
- `research_chunks` — `id`, `report_id`, `agent`, `text`, `citations` (jsonb), `embedding vector(1536)`, `source`.

`source` (`web` | `corpus`) exists from the first migration so that, once retrieval is on, corpus-derived claims can never be re-ingested as fresh findings — otherwise a wrong finding from report #10 gets retrieved into report #50, repeated by the judge, and re-ingested as corroborated. One column now, unfixable later.
- `usage_counters` — `user_id`, `period`, `count`.

## Implementation Phases

### Phase 1 — Foundation
- [ ] Repo scaffold: `web/` + `api/`, docker-compose with Postgres + pgvector.
- [ ] SQLAlchemy models + Alembic migration (incl. `CREATE EXTENSION vector` and HNSW indexes).
- [ ] Auth wired both sides.
- [ ] `POST /reports` → row insert → returns id (no research yet).

### Phase 2 — Pipeline
- [ ] Perplexity client (retry, timeout, citation extraction).
- [ ] Four research node prompts; `StateGraph` with reducer-backed fan-in.
- [ ] Judge prompt + Pydantic report schema, structured output.
- [ ] `persist` node + status transitions + failure handling.
- [ ] Checkpointer wired so partial runs are resumable.

### Phase 3 — Corpus ingest
- [ ] OpenAI embedding client (batched).
- [ ] `ingest` node: ideas + entities (domain upsert) + chunks.
- [ ] Backfill script for any reports produced before ingest landed.
- [ ] Corpus stats endpoint (row counts, growth) — proves the asset is accumulating.

### Phase 4 — Product surface
- [ ] Progress streaming to the frontend.
- [ ] Report page, history, public share links.
- [ ] Quota enforcement, input guardrails, prompt caching on the judge rubric.
- [ ] Golden-set eval: ~15 ideas with known outcomes, check score ordering is sane.

## Open Questions
- **Execution model:** in-process FastAPI background task with a Postgres checkpointer, a separate worker (arq/Celery), or LangGraph Platform/Server. Blocks Phase 1.
- **Hosting + auth provider.**
- Judge model tier — measure `claude-sonnet-5` against `claude-opus-5` on the golden set before committing.
- Sonar tier: `sonar` vs `sonar-pro`.
- Chunking strategy for `research_chunks`: whole sub-agent answer as one row, or split per claim? Per-claim is better for retrieval, more rows, needs a splitter.
- When retrieval turns on: how do we stop the corpus echoing itself (a wrong finding from report #10 reinforcing itself through report #200)?
