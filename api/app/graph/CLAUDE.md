# app/graph/ — the LangGraph pipeline

Where a report is actually produced: four Perplexity Sonar researchers fan out from START, a Claude judge synthesises their dossiers into a structured scored report.

## Files

| Path | Role |
|---|---|
| `state.py` | `ReportState` — shared state; `dossiers` and `degraded_agents` both carry reducers |
| `schema.py` | The judge's output contract: `JudgeReport`, `Subscores`, `SCORE_WEIGHTS`, citation validation |
| `build.py` | `build_graph(checkpointer, research_client, judge)` → compiled graph. Wiring lives here |
| `nodes/prompts.py` | The four research prompts + the judge system/user prompts |
| `nodes/research.py` | `make_research_node(agent, client)` — one factory, four nodes. Retry + fail-soft |
| `nodes/judge.py` | Citation table construction, dossier rendering, judge call, score computation |

## Shape

```
START → {research_competitors, research_incumbents,
         research_market_signals, research_graveyard} → judge → END
```

Four separate nodes with static edges from START, deliberately *not* one node calling `asyncio.gather`. Separate nodes are what let the checkpointer resume a partially-completed run, and what let a planner-driven `Send` fan-out drop in later without rewriting the graph.

**There is no `persist` node.** `PLAN.md` originally specified one; it was dropped because it contradicts the "nodes never touch the database" invariant below, and the runner already did the work. See the Phase 2 notes in `PLAN.md` for the crash-window this leaves open.

## Invariants

- **`dossiers` and `degraded_agents` must keep their `operator.add` reducers.** Four nodes write to both concurrently; without a reducer the last one to finish silently overwrites the other three.
- **Nodes never touch the database.** They report progress via `get_stream_writer()`; `app/runner.py` consumes `stream_mode=["custom", "values"]` and persists. This keeps nodes testable and is the seam SSE plugs into in Phase 4.
- **`thread_id` is the report ID**, one thread per report — that's what makes a crashed run resumable.
- **Clients are injected, never constructed here.** `build_graph` takes `research_client` and `judge` so the default test suite drives the whole pipeline with fakes at zero API spend.

## The custom-event protocol

Two event shapes travel over `stream_mode="custom"`. The runner branches on which key is present:

| Event | Emitted by | Runner behaviour |
|---|---|---|
| `{"agent_done": "<agent>"}` | each research node, on completion (success *or* degradation) | adds to a set, writes `step = "researching (n/4)"` |
| `{"step": "<text>"}` | the judge node | writes `step` verbatim |

Research nodes deliberately do **not** emit their own `step` string. Four concurrent writers would give last-writer-wins, and a user watching would see progress flicker between agent names and appear to go backwards. Aggregation belongs in the runner, which owns presentation.

## Failure semantics

**Research is fail-soft.** A node that cannot get a dossier returns an empty one and adds itself to `degraded_agents`; the run continues. `RetryPolicy` is *not* used for this — see below — and hard-failing would discard the three Perplexity calls that succeeded over one that was never going to recover. `degraded_agents` surfaces in the report JSON so a thin report is never presented as a complete one.

**The floor:** the judge node raises if *all four* dossiers are empty. A report built on nothing is not degraded, it is not a report.

**Retry lives inside the node, not as a LangGraph `RetryPolicy`.** This is the non-obvious part: research nodes swallow their own exceptions to keep the run alive, so they never raise — and a `RetryPolicy` on a node that never raises never fires. It would be dead config. `_research_with_retry` in `research.py` wraps the client call *underneath* the fail-soft catch, so transient timeouts cost a retry and only persistent failures reach the degraded path. Tuned by `RESEARCH_RETRY_ATTEMPTS` / `RESEARCH_RETRY_BASE_DELAY_S`.

## Citations are integers, not URLs

Before the judge is called, every dossier's source URLs are flattened into one deterministic, deduped table (ordered by canonical agent order, so it's stable regardless of which node finished first). Each dossier is rendered with its own `[n]` markers, and the schema requires `sources: list[int]` on every competitor, risk, and differentiation angle.

**The judge physically cannot emit a URL.** An LLM asked to write source URLs writes plausible ones that do not exist — attached to specific factual claims about real companies, the highest-stakes place for a fabricated source. An out-of-range index fails `validate_citation_indices` and fails the run rather than rendering as a broken link.

Honest limit: Sonar's citations are per-*response*, not per-*sentence*, so an index means "this came from the competitors dossier, which drew on these sources" — not "this exact sentence came from source 7."

## The Perplexity citation shape (verified)

Confirmed against a live `sonar-pro` response, langchain-perplexity 1.4.0:

```
response_metadata -> {"model_name", "search_context_size"}   # no citations here
additional_kwargs -> {"citations", "search_results"}         # both present
```

Citations arrive on **`additional_kwargs`**, not `response_metadata` — `extract_citations` checks `response_metadata` first only as a cheap hedge in case the wrapper relocates them. `search_results` is a list of dicts with `url`/`title`; `citations` is a flat list of the same URLs. A single-query probe returned 17.

This is the one payload whose exact shape the product depends on: it becomes `research_chunks.citations` and every citation index in the report, and the LangChain wrapper (not the raw API) decides it. `tests/test_live.py` is what keeps it honest — treat a citation failure there as the contract having moved, not as flakiness.

**`search_context_size` came back `low`** (the wrapper's default). That is a research-depth lever we are currently leaving on its weakest setting; worth revisiting when tuning report quality.

## The score is computed, not judged

The judge emits five subscores and **no overall score**; `Subscores.weighted_score()` takes a weighted mean using `SCORE_WEIGHTS`. LLM holistic scores drift with prompt wording, cluster in the 60-75 band, and can contradict their own subscores with nothing to catch it. A weighted mean makes the 0-100 scale comparable across runs, and makes retuning free — historical reports can be re-scored from stored subscores without re-running the judge.

**Every subscore must stay higher-is-better.** `competitive_intensity` was renamed `competitive_headroom` for exactly this reason: a weighted mean over a mixed-direction field is silently wrong, and a prompt sentence is not strong enough to hold that line. If you add a subscore, add it to `SCORE_WEIGHTS` and check the weights still sum to 1.0.

## Adding a node

1. Write it in `nodes/`, taking `ReportState` and returning a partial dict — never mutate and return state.
2. Register it in `build.py` with `add_node` + edges.
3. If it writes to a list that other nodes also write to, that field needs a reducer.
4. Emit `{"step": "..."}` through the stream writer if the UI should show progress — and if several instances run concurrently, emit a completion fact instead and let the runner aggregate.
