# Vercel Deployment

This repo can deploy directly to Vercel from GitHub. You do not need a separate
repository.

## Deployment Shape

The Vercel deployment uses the existing FastAPI app:

- `api/index.py` is the Vercel entrypoint.
- It imports `event_venue_operator.server:app`.
- `vercel.json` routes incoming paths to that ASGI entrypoint so FastAPI can
  handle `/` and `/api/*`.
- Requests for existing files, such as `static/*`, are served directly by
  Vercel through the `handle: "filesystem"` route.
- `.python-version` keeps local Python tooling on 3.12; confirm the Vercel
  Python runtime is also set to 3.12 in the project environment.
- The repo uses `pyproject.toml` for dependencies and does not include
  `requirements.txt`; confirm the Vercel build installs the project package and
  dependencies from `pyproject.toml`.
- The local development path is unchanged: `uv run python -m event_venue_operator.server`.

The hosted site should be treated as a public demo surface:

- Tabs 1-3: guided deterministic narrative.
- Tab 4: live Atlas retrieval and optional Langfuse traces.
- Full LangGraph agent execution remains a script-based validation path unless
  a protected hosted endpoint is intentionally added later.

The FastAPI app currently allows permissive CORS for demo convenience. Restrict
CORS and add access controls before enabling public LLM-backed, write-capable,
or operator-action endpoints.

## Account Setup

1. Create or sign in to a Vercel account.
2. Connect GitHub.
3. Import `mikikob-mongodb/event-venue-operator`.
4. Deploy from a branch first, not production `main`.
5. Add environment variables to the Preview environment.
6. Promote to Production only after the preview passes validation.

## Environment Variables

Required for the hosted backend proof points:

```bash
MONGODB_URI=<atlas-connection-string>
MONGODB_DATABASE=event_venue_operator
MONGODB_APP_NAME=devrel-github-atlas-langgraph-marktechpost
VOYAGE_API_KEY=<voyage-key>
```

Optional:

```bash
LANGFUSE_PUBLIC_KEY=<langfuse-public-key>
LANGFUSE_SECRET_KEY=<langfuse-secret-key>
LANGFUSE_HOST=https://cloud.langfuse.com
```

Only add `ANTHROPIC_API_KEY` if the hosted deployment is meant to expose Vision
RAG or other LLM-backed endpoints. For a public demo link, it is safer to leave
LLM-backed endpoints unconfigured until there is an access-control or usage plan.

Note: `.env.example` includes `ANTHROPIC_API_KEY` for the local POC scripts; you
can omit it in Vercel Preview/Production unless you intend to enable
`/api/vision-rag/*`.

## Preview Validation

After Vercel creates a preview URL:

1. Open `/` and confirm the guided UI loads.
2. Open `/api/health` and confirm MongoDB reports `up`.
3. Use the **Live Backend** tab to run Vector Search.
4. Use the **Live Backend** tab to run Hybrid Search.
5. If Langfuse keys are configured, confirm traces named `api.search` and
   `api.hybrid_search` appear in Langfuse.

The live LangGraph path is still validated locally with:

```bash
uv run python scripts/run_poc.py
```

or, for a local Grove setup:

```bash
ANTHROPIC_API_KEY=local-placeholder-use-grove-later \
UV_CACHE_DIR=.uv-cache uv run python local/run_poc_with_grove.py
```
