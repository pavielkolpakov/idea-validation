# app/graph/ — the LangGraph pipeline

Where a report is actually produced. Phase 1 ships a stub; Phase 2 replaces the node body without restructuring anything around it.

## Files

| Path | Role |
|---|---|
| `state.py` | `ReportState` — shared state, including the reducer-backed `dossiers` field |
| `build.py` | `build_graph(checkpointer)` → compiled graph. Wiring lives here |
| `nodes/stub.py` | **Throwaway.** Fake 3s run producing a canned report. Deleted in Phase 2 |

## Current shape

```
START → stub → END
```

## Target shape (Phase 2)

```
START → {competitors, incumbents, market_signals, graveyard} → judge → persist → ingest → END
```

Four research nodes with static edges from START — deliberately *not* one node calling `asyncio.gather`. Separate nodes are what let the checkpointer resume a partially-completed run, and what let a planner-driven `Send` fan-out drop in later without rewriting the graph.

## Invariants

- **`dossiers` must keep its `Annotated[list, operator.add]` reducer.** Four nodes write to it concurrently in Phase 2; without the reducer the last one to finish silently overwrites the other three. It already carries the reducer in Phase 1 even though only one node exists.
- **Nodes never touch the database.** They report progress via `get_stream_writer()` (`{"step": "..."}`); `app/runner.py` consumes `stream_mode=["custom", "values"]` and persists it. This keeps nodes testable and is the same seam SSE plugs into in Phase 4.
- **`thread_id` is the report ID**, one thread per report — that's what makes a crashed run resumable.
- Research nodes get a `RetryPolicy`; Perplexity timeouts are transient.
- `persist` must run before `ingest` so a corpus-write failure can never cost the user their report. `ingest` swallows its own errors.

## Adding a node

1. Write it in `nodes/`, taking `ReportState` and returning a partial dict — never mutate and return state.
2. Register it in `build.py` with `add_node` + edges.
3. If it writes to a list that other nodes also write to, that field needs a reducer.
4. Emit `{"step": "..."}` through the stream writer if the UI should show progress.
