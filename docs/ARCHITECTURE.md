# Architecture

This document explains the why behind the how. For just-run-it instructions, see the [README](../README.md).

## Overview

The system is an operator-facing dashboard backed by a LangGraph agent that reads from and writes to a single MongoDB Atlas cluster. That cluster holds four distinct kinds of data, unified under one query surface:

1. **Operational records**: Guests, visits, venue status, weather events, venues
2. **Semantic memory vectors**: Prior-visit memories and fleet-wide patterns, indexed for vector search
3. **Session checkpoints**: LangGraph state snapshots scoped by visit_id
4. **Time-series wait data**: Historical queue or dwell-time signals

The architectural claim: no sync jobs, no second database, no glue code. The agent's memory and the operator's operational data live in the same database, queryable together.

## The agent loop

The agent follows a five-node graph: perceive → plan → hitl_gate → act → reflect.

```
┌─────────┐    ┌──────┐    ┌───────────┐    ┌─────┐    ┌─────────┐
│ perceive│───▶│ plan │───▶│ hitl_gate │───▶│ act │───▶│ reflect │───▶ END
└─────────┘    └──────┘    └───────────┘    └─────┘    └─────────┘
     │              │             │             │            │
     ▼              ▼             ▼             ▼            ▼
  Reads from    Calls Claude   Pass-through  Executes    Writes new
  memory_store  with context   for MVP       tools       signals to
  + venue status              (auto-approve)            memory_store
```

### perceive

Gathers context from memory and operational data. Performs multiple vector searches against the guest namespace (`("guests", "fam_001")`) and fleet namespace (`("fleet", "event_001")`). Retrieves:

- Prior-event memories (court delays, rain incidents, wayfinding issues, hospitality misses, satisfaction signals)
- Stable preferences for Mikiko and Nina
- Operator patterns for covered routing, weather response, and hospitality protection
- Current venue status and active weather events from operational collections

Returns a `perception` dict that the plan node consumes.

### plan

Invokes Claude Sonnet 4.6 with the perception context. The system prompt instructs Claude to:

1. Acknowledge what went wrong on previous visits
2. Plan around those failure modes proactively
3. Accommodate each persona's specific needs
4. Build in contingencies (covered routing, indoor hospitality, protected reservations)

Claude generates a venue plan by calling the `update_itinerary` tool. If a weather event is active, Claude also calls `book_reservation` to secure covered hospitality proactively.

The plan node extracts "callback cards" from itinerary annotations—references to prior-visit incidents that show "what went wrong before → what we're doing differently today."

### hitl_gate

Human-in-the-loop approval gate. For the current implementation, this is a pass-through that auto-approves all actions. The architecture includes it because:

- High-stakes actions (refunds, upgrades, external notifications) should require operator approval
- The graph structure supports conditional edges for approve/deny/escalate paths
- V2 will activate this gate for actions above a risk threshold

### act

Executes the approved action(s). Calls tool functions that write to operational collections:

- `update_itinerary`: Writes the planned venue itinerary/actions to the `visits` collection
- `book_reservation`: Creates a reservation document in the `visits` collection

Every tool execution is logged to `agent_actions` for audit trail.

### reflect

Observes the outcome and writes new inferences to the guest namespace. For example, if the agent successfully generated a proactive rain-delay plan, it records that signal so future visits know these personas received proactive support on Visit 3.

This is how memory accumulates over time: each visit potentially adds new signals that inform the next visit.

## Data model

### Operational collections (6)

| Collection | Purpose | Writers | Readers |
|------------|---------|---------|---------|
| `guests` | Visitor/persona profiles and preference flags | Seed script, admin | perceive node |
| `visits` | One doc per visit with planned and actual itinerary, reservations | act node tools | UI, perceive node |
| `venue_status` | Current state of courts and venue locations. | External system, triggers | perceive node, UI |
| `occupancy_history` | Time-series queue or dwell-time data. | External system | Aggregator (future) |
| `weather_events` | Weather alerts and forecasts | External system, triggers | perceive node, UI |
| `agent_actions` | Audit log of every agent decision | act node | UI, aggregator (future) |

### LangGraph-managed collections (3)

| Collection | Purpose | Managed by |
|------------|---------|------------|
| `memory_store` | Semantic memory with vector embeddings | MongoDBStore |
| `checkpoints` | Graph state snapshots | MongoDBSaver |
| `checkpoint_writes` | Node-level writes within checkpoints | MongoDBSaver |

### Memory namespaces

The `memory_store` collection holds three namespaces, distinguished by a `namespace` field:

**`("guests", guest_id)`**: Per-visitor/persona memory. Contains:
- Visit 1 incidents for Mikiko: suspended court, wayfinding friction, missed match start, low satisfaction
- Visit 2 incidents for Nina: rain delay, missed hospitality window, low satisfaction
- Stable preferences for Mikiko's first-timer path and Nina's premier hospitality needs

**`("fleet", event_id)`**: Operator-wide patterns. Contains:
- Redirect patterns for outdoor court suspensions
- Weather response patterns for covered routing and indoor hospitality
- First-time visitor guidance patterns

**`("docs", event_id)`**: Visual operational documents. Contains:
- Accessibility and routing references
- Allergen and hospitality reference material
- Weather response and emergency planning documents

The guest and fleet namespaces are retrieved by the live agent at perception time. The docs namespace powers the visual RAG endpoint.

## Memory design decisions

### Why Voyage multimodal embeddings

Voyage embeddings support the operational memory and visual-document retrieval paths. The model produces normalized vectors, so cosine similarity is appropriate.

### Why 1024 dimensions

Voyage supports multiple dimension options. 1024 is the recommended default—a balance between retrieval quality and index size. Smaller dimensions (512) would reduce storage but degrade recall on nuanced queries.

### Why two namespaces instead of two collections

A single collection with namespace-based filtering is simpler to operate:
- One vector search index instead of two
- One collection to monitor and back up
- Aggregation pipelines can retrieve from both namespaces in one round-trip

The filter field `namespace_prefix` (written by MongoDBStore) scopes queries efficiently.

### Why MongoDBStore instead of a separate vector database

This is the core architectural claim. If the agent's memory lived in Pinecone or Weaviate, every action that touches both operational data and memory would require:
- Two database connections
- Potential consistency issues (memory says X, operational data says Y)
- Sync jobs to keep them aligned

With MongoDB as the single backend, the agent can join operational data with semantic memory in a single query. The demo doesn't exercise complex joins, but the architecture enables them.

## Server layer

### FastAPI server (`src/event_venue_operator/server.py`)

The current demo surface is a FastAPI server that serves the static UI and
exposes live backend proof-point endpoints:

| Endpoint | Purpose |
|----------|---------|
| `GET /` | Serves the static HTML UI |
| `GET /favicon.ico` | Serves the browser tab icon |
| `GET /api/health` | MongoDB ping for sanity checks |
| `GET /api/search` | Real Atlas Vector Search over memory_store |
| `GET /api/hybrid-search` | Vector + lexical hybrid retrieval over memory_store |
| `POST /api/unified-search` | Cross-namespace search with profile-fact joins |
| `GET /api/vision-rag/documents` | Lists indexed visual documents |
| `POST /api/vision-rag/query` | Retrieves relevant visual documents and asks Claude Vision to answer |
| `GET /api/observability/status` | Reports whether Langfuse tracing is configured |
| `GET /api/stats` | Collection counts for the architecture tab |
| `GET /api/debug/embed` | Embed a string via Voyage (Vector Inspector) |
| `GET /api/debug/similarity` | Compute cosine similarity between two strings |

The static UI is mostly scripted for stage reliability. The API endpoints,
seed scripts, smoke test, and `scripts/run_poc.py` exercise the live Atlas,
Voyage, Claude, LangGraph, and optional Langfuse paths.

## UI model

The demo UI is a single HTML file (`static/index.html`) with client-side
JavaScript. Three tabs drive the stage narrative:

1. **Venue Ops**: Live tournament dashboard with courts, hospitality, KPIs, and rain forecast.
2. **Scenario (rain)**: Click-by-click agent walkthrough for Nina and Mikiko personas.
3. **Final Outcomes**: End-of-day summary and memory write-back story.

A fourth **Live Backend** tab keeps tutorial validation separate from the
operator narrative. It calls live retrieval endpoints and surfaces the top
memory returned by Atlas while emitting optional Langfuse traces when keys are
configured.

The full LangGraph path is validated from `scripts/run_poc.py`, which emits a
run-level `langgraph.run_agent` Langfuse observation when keys are configured.

The split between real and scripted:

| Feature | Real or Scripted |
|---------|------------------|
| Main stage UI values | Scripted |
| Scenario progression | Scripted |
| Persona cards | Scripted |
| `/api/search` | Real (Atlas Vector Search) |
| `/api/hybrid-search` | Real (vector + lexical hybrid retrieval) |
| `/api/unified-search` | Real (Atlas Vector Search + profile joins) |
| `/api/vision-rag/query` | Real (Atlas Vector Search + Claude Vision) |
| `scripts/run_poc.py` | Real LangGraph execution |

The demo is mostly scripted because predictable pacing on stage beats unpredictable LLM latency. The architecture supports real execution everywhere; the quick demo cashes in "real" only where it's defensible (vector search, embeddings).

## Design decisions

### Why LangGraph

LangGraph provides:
- State machine model that fits the perceive/plan/act/reflect loop
- Built-in checkpointing via MongoDBSaver
- Streaming support for real-time UI updates
- Conditional edges for future hitl_gate branching

The alternative (hand-rolled agent loop) would require reimplementing checkpointing and streaming.

### Why FastAPI + static HTML instead of Next.js

The quick demo optimizes for:
- No build step (copy files to a new machine, run the server)
- Single static HTML ships easily
- SSE works cleanly for streaming
- Minimal JavaScript surface (vanilla JS, no framework)

This fits a DevRel demo. A production operator console would likely use a richer framework.

### Why Claude Sonnet 4.6 as the default LLM

Good tool-use reliability, fast enough for stage latency, cost-effective for development iteration. Opus 4.7 is available as a fallback for harder planning problems but is rarely needed.

### Why four tabs instead of one dense dashboard

Progressive disclosure. Each tab has a single purpose. The alternative—one information-dense dashboard—overwhelms the audience mid-narration. The presenter clicks through tabs as the story unfolds.

## Extension points

### Adding a memory category

1. Add the category to `MEMORY_CATEGORIES` in `config.py`
2. Add seed entries in `seed.py` with the new category
3. Re-run `seed_data.py`
4. Optionally update the UI to display the category distinctly

### Wiring another trigger to the real agent

1. Add a route in `server.py` (e.g., `POST /trigger/weather_alert`)
2. In the handler, create the weather event in the database, then call `run_agent()` or `stream_agent()`
3. Add a button in the UI that calls the new endpoint
4. Handle the streaming response in the UI

### Adding a fleet-wide pattern

1. Add the pattern to `FLEET_PATTERNS` in `seed.py`
2. Re-run `seed_data.py`
3. The new pattern is immediately retrievable via `store.search(("fleet", "event_001"), ...)`

### Supporting a second venue or event

1. Add a new venue/event identifier constant.
2. Create a new fleet/operator namespace for that identifier.
3. Seed operator patterns for the new venue or event.
4. Add per-venue filtering in server queries and UI.

### Adding a new node to the graph

1. Define the node function in `nodes.py`
2. Add the node to the graph in `graph.py` via `graph.add_node()`
3. Wire edges appropriately (e.g., insert between plan and hitl_gate)
4. Update the state schema in `state.py` if the node produces new fields

## Scope boundaries

| Boundary | Reason |
|----------|--------|
| Stage demo triggers are scripted | Stage reliability and tutorial repeatability |
| Change streams are not wired to the UI | V1 focuses on Atlas memory, hybrid search, and the runnable LangGraph path |
| `hitl_gate` auto-approves actions | The graph keeps the approval insertion point visible without adding production workflow complexity |
| Single event scenario | Narrative focus for the tutorial and MarkTechPost write-up |
| No CI or eval harness | Production hardening is outside the tutorial scope |

## Further reading

- [README.md](../README.md) — quickstart and project overview
- [docs/LANGGRAPH.md](LANGGRAPH.md) — live agent walkthrough
- [docs/features.md](features.md) — tech stack feature inventory
- [LangGraph documentation](https://langchain-ai.github.io/langgraph/)
- [MongoDB Atlas Vector Search](https://www.mongodb.com/docs/atlas/atlas-vector-search/)
- [Voyage AI](https://www.voyageai.com/)
