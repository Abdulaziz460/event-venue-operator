# Event Venue Operator — Tech Stack Feature Inventory

| | |
|---|---|
| **Audience for this doc** | Developers working on the Event Venue Operator repo. |
| **Companion docs** | `README.md`, `ARCHITECTURE.md` |
| **Purpose** | A precise inventory of which features the demo actually exercises, so a developer can map observed behavior back to the underlying MongoDB, LangGraph, and Claude primitives. |

This is not a feature brochure for each tool. Items marked "V1" are part of the current runnable tutorial path. Items marked "Extension" exist as code hooks or clear follow-on work, but are intentionally outside the V1 tutorial scope.

---

## MongoDB Atlas

| Feature | How the demo uses it | Stage |
|---|---|---|
| **Atlas Vector Search** | Backs the `MongoDBStore` long-term memory. Guest preference embeddings and operator patterns are retrieved via vector similarity. | V1 |
| **Hybrid retrieval** | `/api/hybrid-search` combines Atlas Vector Search with lexical matching over memory text, returning vector, lexical, and combined scores. | V1 |
| **Visual-document retrieval** | `scripts/seed_visual_docs.py` embeds operational images, and `/api/vision-rag/query` retrieves relevant images for Claude Vision. | V1 |
| **Standard indexes** | Query performance on guest, visit, venue status, and timestamp fields. | V1 |
| **Operational read/write** | CRUD on operational collections via `pymongo`, including visits, reservations, weather events, and agent action logs. | V1 |
| **Unified operational + vector database** | One Atlas cluster serves operational queries, vector search, agent checkpoints, and long-term memory. | V1 |
| **Change Streams** | Listener utilities exist for venue status and weather events, but the V1 UI and tutorial do not depend on real-time triggers. | Extension |
| **Time Series Collections** | Time-series setup is available for historical venue metrics, but it is not central to the V1 tutorial path. | Extension |
| **Aggregation Pipeline** | Used for search and profile-fact joining; broader context-engineering joins are an extension path. | V1 / Extension |

---

## `langgraph-checkpoint-mongodb` (MongoDBSaver)

| Feature | How the demo uses it | Stage |
|---|---|---|
| **`MongoDBSaver`** | The checkpointer class. Persists LangGraph agent state to Atlas after node execution. Thread-scoped by `visit_id`. | V1 |
| **`from_conn_string`** | Initialization pattern from the MongoDB URI. Standard usage. | V1 |
| **Automatic checkpointing** | The framework writes to `checkpoints` and `checkpoint_writes` during graph execution. | V1 |
| **Thread resumption** | Each visit has a unique `thread_id`, so graph state can be scoped to a visit. | V1 |
| **Time-travel retrieval** | Checkpoint replay/rewind is a natural follow-on, but not exposed in the V1 UI. | Extension |
| **Async support (`AsyncMongoDBSaver`)** | Async checkpointer support is a future scale path, not part of the V1 tutorial flow. | Extension |

---

## `langgraph-store-mongodb` (MongoDBStore) — the long-term memory pillar

| Feature | How the demo uses it | Stage |
|---|---|---|
| **`MongoDBStore`** | The long-term memory store. Persists memories that outlive any single graph run. | V1 |
| **`VectorIndexConfig`** | Configures the store's vector index for semantic retrieval: dimensions, embedding model, and filters. | V1 |
| **Namespacing** | `("guests", guest_id)` for persona memory, `("fleet", event_id)` for operator-level patterns, and `("docs", event_id)` for visual documents. | V1 |
| **`put()`** | Writes memories and visual-document entries. Used by seed scripts and the `reflect` node. | V1 |
| **`search()`** | Semantic retrieval with vector similarity over a namespace. Used by the `perceive` node and search endpoints. | V1 |
| **Fleet-level aggregation writes** | Background aggregation of completed visits into new fleet patterns is a future extension. | Extension |

---

## LangGraph (core framework)

| Feature | How the demo uses it | Stage |
|---|---|---|
| **`StateGraph`** | The graph primitive. Nodes + edges define the perceive → plan → hitl_gate → act → reflect loop. | V1 |
| **Typed state** | Custom `TypedDict` state tracking perception payload, proposed action, approval status, and inferred signals. | V1 |
| **Nodes** | Five nodes: `perceive`, `plan`, `hitl_gate`, `act`, `reflect`. | V1 |
| **Linear edges** | `START → perceive → plan → hitl_gate → act → reflect → END` for the tutorial flow. | V1 |
| **`compile()` with checkpointer + store** | Graph is compiled with both `MongoDBSaver` and `MongoDBStore`, wiring Atlas into LangGraph as both session-state and long-term-memory backend. | V1 |
| **Thread config** | `configurable.thread_id` passed with every invocation. Ties the graph run to a visit. | V1 |
| **Streaming (`astream`)** | A natural UI extension; the current V1 UI uses a deterministic walkthrough instead. | Extension |
| **Conditional edges / interrupts** | Production-grade approve, deny, escalate, and resume flows are represented by the `hitl_gate` insertion point but not activated in V1. | Extension |
| **Checkpoint time-travel** | Operator rewind/replay is a future extension. | Extension |

---

## Claude (via `init_chat_model`)

| Feature | How the demo uses it | Stage |
|---|---|---|
| **Claude Sonnet 4.6** | Default model for the `plan` and `reflect` nodes. Balance of speed and reasoning quality. | V1 |
| **Claude Sonnet 4.5** | Used by the Vision RAG endpoint for visual-document question answering. | V1 |
| **Tool use / function calling** | The agent exposes `update_itinerary` and `book_reservation` as callable tools. | V1 |
| **System prompts** | Operator-framed persona prompt for each node, with planning focused on proactive rain-delay recovery. | V1 |
| **Multi-turn context within a thread** | Claude sees graph state and checkpointed context for a visit. | V1 |
| **Streaming responses** | Progressive response streaming is a future UI extension, not required for the current guided demo. | Extension |

---

## `langchain-voyageai`

| Feature | How the demo uses it | Stage |
|---|---|---|
| **`voyage-multimodal-3.5` model** | Embeds text memories and visual documents into the same 1024-dimensional space. | V1 |
| **Custom embedding wrapper** | `VoyageMultimodalEmbeddings` supports both text and image embedding calls used by the memory store and visual-document seed path. | V1 |
| **Embedding on write + query** | Seed scripts compute embeddings on write; search endpoints compute embeddings on query. | V1 |

---

## `langchain-mongodb`

| Feature | How the demo uses it | Stage |
|---|---|---|
| **Transitive dependency** | Backs parts of the MongoDB/LangChain integration stack. | V1 |

The tutorial uses `MongoDBStore` and custom API endpoints for retrieval rather than exposing `MongoDBAtlasVectorSearch` as a named agent tool.

---

## Langfuse

| Feature | How the demo uses it | Stage |
|---|---|---|
| **Optional trace capture** | Enabled when `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` are set. Disabled cleanly otherwise. | V1 |
| **Retrieval spans** | `/api/search` and `/api/hybrid-search` emit Langfuse observations around retrieval calls. | V1 |
| **Agent run span** | `scripts/run_poc.py` emits a run-level `langgraph.run_agent` observation for the live LangGraph path. | V1 |
| **Configuration status** | `/api/observability/status` reports whether Langfuse is configured for the running server. | V1 |
| **Smoke-test coverage** | `scripts/smoke_test.py` checks the observability status endpoint so missing config is explicit. | V1 |

Langfuse is not required to run the demo. Add keys to `.env` to emit retrieval
endpoint traces and a run-level LangGraph trace during local runs or rehearsal.
The current V1 repo does not trace individual graph nodes or the Vision RAG
endpoint.

---

## FastAPI + Static HTML — the UI surface

| Feature | How the demo uses it | Stage |
|---|---|---|
| **FastAPI server** | Serves the static demo and exposes live backend endpoints from one process. | V1 |
| **Static HTML/CSS/JS** | Primary stage surface. No frontend build step; deterministic enough for narration. | V1 |
| **Three-tab story flow + Live Backend tab** | Venue Ops, Scenario (rain), and Final Outcomes match the stage narrative; Live Backend validates retrieval and optional Langfuse traces. | V1 |
| **API endpoints** | `/api/search`, `/api/hybrid-search`, `/api/unified-search`, `/api/vision-rag/query`, `/api/stats`, and debug endpoints exercise the live backend separately from the scripted UI. | V1 |
| **Smoke test** | `scripts/smoke_test.py` validates health, vector search, hybrid search, visual docs, Vision RAG, Langfuse wiring, and stats against the running server. | V1 |
| **Atlas appName** | MongoDB connections use `MONGODB_APP_NAME`, defaulting to `devrel-github-atlas-langgraph-marktechpost` for GitHub attribution. | V1 |

The static UI is the locked stage surface for this repo. V2 may wire more of
the UI to live endpoints, but V1 treats the UI as the guided narrative and the
API/scripts as the backend proof points.

---

## Python ecosystem

| Feature | How the demo uses it | Stage |
|---|---|---|
| **`pymongo` / `motor`** | MongoDB drivers used directly for operational reads/writes and indirectly by the LangGraph integrations. | V1 |
| **`pydantic`** | State schemas and tool input schemas. | V1 |
| **`python-dotenv`** | Local env config for URIs and API keys. | V1 |
| **`asyncio`** | Useful for future concurrent trigger handling; not central to the V1 tutorial flow. | Extension |

---

## Cross-cutting view — features mapped to the three pillars

The architecture rests on three pillars. Here's which features land under each.

**Pillar 1: Agent memory (primary).**
- `MongoDBStore` with namespaced guest and fleet semantic memory
- `VoyageAIEmbeddings` for semantic retrieval
- Atlas Vector Search indexes backing the store
- `MongoDBSaver` for agent session state checkpointed per visit (supports memory but is a separate layer from the three semantic tiers)
- LangGraph's `reflect` node pattern for writing inferred signals
- Aggregation pipeline joining semantic memory tiers at decision time

**Pillar 2: Live operational context.**
- `venue_status` and `weather_events` operational collections
- LangGraph's `perceive` node reading current operational state
- Atlas-backed search endpoints that prove retrieval behavior separately from the scripted UI
- Change stream listener utilities as a future real-time trigger path

**Pillar 3: MongoDB as the agentic stack backend.**
- Converged operational + vector database (one connection, four kinds of state)
- First-party LangGraph integrations (`langgraph-checkpoint-mongodb`, `langgraph-store-mongodb`) — both MongoDB-authored
- Atlas-native vector indexes with Voyage embeddings
- Change streams available as the future event backbone (no Kafka, no separate broker)
- Aggregation pipeline as the context engineering primitive

---

## Alternatives considered but not used

Technologies in the same category that the demo deliberately does not depend on, and the reasoning behind each choice.

| Thing we're not using | Why |
|---|---|
| **Claude Agent SDK** | Chose LangGraph for first-class HITL, graph, and checkpointing primitives. The SDK treats session state as ephemeral and would require reimplementing what LangGraph ships with. Not a knock on the SDK — different tool for a different job. |
| **LiteLLM** | Not used in this build. OpenRouter is the preferred fallback if model routing is needed. |
| **Mem0 / Zep / Letta** | Introducing a third-party memory service contradicts the architectural claim that Atlas *is* the memory system. |
| **Kafka / external stream broker** | Change streams are the stream broker for operational event propagation in this demo. |
| **LangSmith** | Langfuse is the chosen LLMOps tool for this build. LangSmith is a fine alternative; not mixed. |
| **Multimodal video** | Not needed for this tutorial. The demo uses multimodal embeddings for image/document retrieval, but does not process video. |
| **LangGraph Agent Teams / multi-agent** | Single agent for MVP. V2 may add a background fleet-aggregator, but not interactive multi-agent. |
| **Next.js / React / shadcn** | Rejected for V1. The demo favors one static HTML file plus FastAPI so setup remains simple and stage pacing is predictable. |
| **MCP servers** | Not needed for MVP. V2 may expose an operator-backend integration via MCP. |
| **AG-UI protocol** | Deferred per earlier strategy decisions. |
| **Real wait-time / weather APIs** | MVP uses mocked feeds. V2 integrates. |
| **Retrieval-augmented parent-child chunking** | Not relevant to this use case — memories aren't documents. |
