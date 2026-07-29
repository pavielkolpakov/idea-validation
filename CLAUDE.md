# IdeaCheck

Web app that validates startup ideas. A user submits an idea; four sub-agents research it in parallel via Perplexity Sonar; a Claude judge synthesizes a structured report with a 0-100 score. Every run also writes into a Postgres + pgvector corpus (ideas, companies, research chunks) that **V1 deliberately does not read from** — the corpus is being accumulated now so retrieval has something worth querying later.

`PLAN.md` is the source of truth for architecture decisions and their rationale. Read it before proposing changes to the design.

## Layout

| Path | What it is |
|---|---|
| `api/` | FastAPI backend, LangGraph pipeline, SQLAlchemy models, Alembic migrations |
| `web/` | Next.js 16 frontend |
| `PLAN.md` | Architecture, decisions + rationale, phase checklist |
| `docker-compose.yml` | Postgres 17 + pgvector (host port **5433**) |

## Commands

```bash
make up        # start Postgres
make migrate   # alembic upgrade head
make api       # uvicorn on :8000
make web       # next dev on :3000
make test      # pytest (creates + migrates ideacheck_test)
make fmt       # ruff check --fix && ruff format
make reset     # drop volume, recreate, re-migrate
```

## Project-wide invariants

- **Postgres is on host port 5433**, not 5432. A local Homebrew Postgres occupies 5432 and silently shadows the container.
- **The corpus is write-only in V1.** Do not add retrieval/RAG without an explicit decision — see `PLAN.md`.
- **`source` (`web` | `corpus`) on `entities` and `research_chunks` is load-bearing.** It exists so corpus-derived claims can never be re-ingested as fresh corroboration once retrieval is on.
- Phase status lives in `PLAN.md`. Phase 1 is complete; Phase 2 replaces the stub graph node with real research.

## Rule: keep these files current

**Whenever you change a module, update that module's `CLAUDE.md` in the same change.** These files exist to make the codebase navigable without reading everything; a stale one is worse than none.

- Change `api/` behaviour, structure, or conventions → update `api/CLAUDE.md`.
- Change the graph, its state, or its nodes → update `api/app/graph/CLAUDE.md`.
- Change `web/` structure or conventions → update `web/CLAUDE.md`.
- Change architecture, add a dependency, or make a decision with a rationale → update this file and/or `PLAN.md`.

Treat it as part of the change, not follow-up work.
