# Observability With Langfuse

Langfuse is optional in this repo. The app runs without Langfuse keys, and the
smoke test treats missing Langfuse configuration as an explicit, valid state.

## What Langfuse Does Today

When `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` are set, the repo creates
Langfuse observations around retrieval API calls and the live LangGraph agent
run.

Currently traced paths:

| Path | Langfuse observation name | What is captured |
|------|---------------------------|------------------|
| `GET /api/search` | `api.search` | Query, namespace, limit, result count, top retrieved memories |
| `GET /api/hybrid-search` | `api.hybrid_search` | Query, namespace, weights, result count, top retrieved memories |
| `scripts/run_poc.py` | `langgraph.run_agent` | Guest ID, visit ID, graph metadata, proposed tools, approval decision, compact outcome summary |

Status endpoint:

| Endpoint | Purpose |
|----------|---------|
| `GET /api/observability/status` | Reports whether Langfuse is enabled and which host is configured |

## What Langfuse Does Not Trace Yet

V1 does not trace:

- Individual LangGraph nodes (`perceive`, `plan`, `hitl_gate`, `act`, `reflect`)
- Claude tool calls inside the LangGraph path
- Vision RAG calls from `/api/vision-rag/query`

Those are useful follow-on extensions, but the current tutorial only claims
Langfuse tracing for retrieval API spans and the run-level LangGraph observation.

## Configure Langfuse

Create a Langfuse project, then add the project keys to `.env`:

```bash
LANGFUSE_PUBLIC_KEY=<your-langfuse-public-key>
LANGFUSE_SECRET_KEY=<your-langfuse-secret-key>
LANGFUSE_HOST=https://cloud.langfuse.com
```

Restart the FastAPI server after editing `.env`; environment values are loaded
when the Python process starts.

## Validate Locally

Start the server:

```bash
uv run python -m event_venue_operator.server
```

Check that the app sees the keys:

```bash
curl "http://127.0.0.1:8000/api/observability/status"
```

Expected response when keys are configured:

```json
{
  "langfuse_enabled": true,
  "langfuse_host": "https://cloud.langfuse.com"
}
```

Generate traced retrieval calls:

```bash
curl "http://127.0.0.1:8000/api/search?q=rain%20hospitality%20problems&namespace=guests"

curl "http://127.0.0.1:8000/api/hybrid-search?q=rain%20hospitality%20reservation&namespace=guests"
```

Then open the Langfuse project dashboard and look for observations named
`api.search` and `api.hybrid_search`.

You can also generate those same calls from the app's **Live Backend** tab. The
tab shows local observability evidence: whether Langfuse is configured, which
observation name was emitted, and a preview of the top retrieval result sent as
trace output. Langfuse remains the system of record for persisted trace history,
timing, and detailed inspection.

Generate a traced LangGraph run:

```bash
uv run python scripts/run_poc.py
```

Then open the Langfuse project dashboard and look for an observation named
`langgraph.run_agent`. The trace output is intentionally compact: it confirms
which graph ran, which tools were proposed, whether the approval gate passed,
and whether the action produced an error without storing full prompts or secrets.

## Smoke Test Coverage

The smoke test calls `/api/observability/status` and confirms the endpoint shape.
It does not assert that traces arrived in Langfuse, because that depends on
external account configuration and network delivery.
