"""
FastAPI app.

Responsibilities:
- Serve the static stage demo as the root page.
- Expose /api/search — real MongoDB Atlas Vector Search against memory_store.
- Expose /api/vision-rag/* — Vision RAG endpoints for visual document Q&A.
- Expose /api/health — quick ping for sanity checks.
- Expose /api/stats — counts across collections so the architecture tab has
  a real number to defend.

Everything else in the UI is scripted; this server only exists to make the
architecture tab defensibly real.
"""
from __future__ import annotations

import base64
import logging
import math
import time
from pathlib import Path

import anthropic
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config, db, observability

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("tpo")

_STATIC_DIR = Path(__file__).resolve().parents[2] / "static"

app = FastAPI(title="Event Venue Operator — Demo")

# Permissive CORS so the mockup running from a file:// URL could also hit us
# during development if needed. For the real demo, everything is same-origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", include_in_schema=False)
def root() -> FileResponse:
    """Serve the static stage demo at /."""
    return FileResponse(_STATIC_DIR / "index.html")


@app.get("/favicon.svg", include_in_schema=False)
def favicon_svg() -> FileResponse:
    """Serve the app favicon as SVG."""
    return FileResponse(_STATIC_DIR / "favicon.svg", media_type="image/svg+xml")


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> FileResponse:
    """Serve the app favicon for browsers that request /favicon.ico."""
    return FileResponse(_STATIC_DIR / "favicon.svg", media_type="image/svg+xml")


@app.get("/api/health")
def health() -> dict:
    """Ping MongoDB. Used by the server at startup and by curl for sanity."""
    ok = db.ping()
    return {"mongodb": "up" if ok else "down"}


@app.get("/api/observability/status")
def observability_status() -> dict:
    """Report whether optional Langfuse tracing is configured."""
    return {
        "langfuse_enabled": observability.enabled(),
        "langfuse_host": config.LANGFUSE_HOST,
    }


@app.get("/api/search")
def search(
    q: str = Query(..., min_length=1, description="Semantic query over memories"),
    namespace: str = Query(
        "guests", description="Which namespace to search: 'guests' or 'fleet'"
    ),
    limit: int = Query(5, ge=1, le=20),
) -> JSONResponse:
    """
    Real vector search over the memory_store collection.

    When Tab 1's search box fires, this endpoint runs:
      1. Voyage 3.5 embeds the query string (1024d).
      2. Atlas Vector Search runs kNN cosine similarity over memory_store,
         scoped to the requested namespace.
      3. Top results are returned with their similarity scores.
    """
    if namespace == "guests":
        ns = config.GUEST_NAMESPACE
    elif namespace == "fleet":
        ns = config.FLEET_NAMESPACE
    else:
        raise HTTPException(400, f"Unknown namespace: {namespace!r}")

    # Shape each result for the frontend: id, score, text, category, visit, severity.
    shaped = []
    try:
        with observability.trace(
            "api.search",
            input={"query": q, "namespace": namespace, "limit": limit},
            metadata={"kind": "vector_search"},
        ):
            results = db.vector_search(ns, q, limit=limit)
            for r in results:
                val = r.get("value", {}) or {}
                visit_id = val.get("visit_id", "stable")
                # The UI expects "visit" to be either "V1"/"V2"/"V3"/"stable"/"FLEET"
                if visit_id == "visit_1":
                    visit_label = "V1"
                elif visit_id == "visit_2":
                    visit_label = "V2"
                elif visit_id == "visit_3":
                    visit_label = "V3"
                elif visit_id == "fleet":
                    visit_label = "FLEET"
                else:
                    visit_label = "stable"
                shaped.append(
                    {
                        "id": r.get("key", "unknown"),
                        "score": round(float(r.get("score", 0.0)), 3),
                        "text": val.get("text", ""),
                        "category": val.get("category", ""),
                        "visit": visit_label,
                        "severity": val.get("severity", "medium"),
                    }
                )
            observability.update(
                output={
                    "count": len(shaped),
                    "top_results": [
                        {
                            "id": item["id"],
                            "score": item["score"],
                            "category": item["category"],
                            "text": item["text"][:220],
                        }
                        for item in shaped[:3]
                    ],
                },
                metadata={"top_key": shaped[0]["id"] if shaped else None},
            )
    except Exception as exc:  # noqa: BLE001
        log.exception("vector_search failed")
        raise HTTPException(500, f"Search failed: {exc}") from exc

    return JSONResponse(
        {
            "query": q,
            "namespace": list(ns),
            "results": shaped,
            "count": len(shaped),
        }
    )


@app.get("/api/hybrid-search")
def hybrid_search(
    q: str = Query(..., min_length=1, max_length=256, description="Hybrid query over memories"),
    namespace: str = Query(
        "guests", description="Which namespace to search: 'guests', 'fleet', or 'docs'"
    ),
    limit: int = Query(5, ge=1, le=20),
    vector_weight: float = Query(0.7, ge=0.0, le=1.0),
) -> JSONResponse:
    """Hybrid retrieval using vector similarity plus lexical matching."""
    if namespace == "guests":
        ns = config.GUEST_NAMESPACE
    elif namespace == "fleet":
        ns = config.FLEET_NAMESPACE
    elif namespace == "docs":
        ns = config.DOCS_NAMESPACE
    else:
        raise HTTPException(400, f"Unknown namespace: {namespace!r}")

    lexical_weight = 1.0 - vector_weight

    shaped = []
    try:
        with observability.trace(
            "api.hybrid_search",
            input={
                "query": q,
                "namespace": namespace,
                "limit": limit,
                "vector_weight": vector_weight,
                "lexical_weight": lexical_weight,
            },
            metadata={"kind": "hybrid_search"},
        ):
            results = db.hybrid_search(
                ns,
                q,
                limit=limit,
                vector_weight=vector_weight,
                lexical_weight=lexical_weight,
            )
            for r in results:
                val = r.get("value", {}) or {}
                shaped.append(
                    {
                        "id": r.get("key", "unknown"),
                        "hybrid_score": round(float(r.get("hybrid_score", 0.0)), 3),
                        "vector_score": round(float(r.get("vector_score", 0.0)), 3),
                        "lexical_score": round(float(r.get("lexical_score", 0.0)), 3),
                        "lexical_matches": r.get("lexical_matches", []),
                        "text": val.get("text", ""),
                        "category": val.get("category", ""),
                        "visit_id": val.get("visit_id"),
                        "severity": val.get("severity", "medium"),
                        "doc_type": val.get("doc_type"),
                    }
                )
            observability.update(
                output={
                    "count": len(shaped),
                    "top_results": [
                        {
                            "id": item["id"],
                            "hybrid_score": item["hybrid_score"],
                            "vector_score": item["vector_score"],
                            "lexical_score": item["lexical_score"],
                            "category": item["category"],
                            "text": item["text"][:220],
                        }
                        for item in shaped[:3]
                    ],
                },
                metadata={"top_key": shaped[0]["id"] if shaped else None},
            )
    except Exception as exc:  # noqa: BLE001
        log.exception("hybrid_search failed")
        raise HTTPException(500, f"Hybrid search failed: {exc}") from exc

    return JSONResponse(
        {
            "query": q,
            "namespace": list(ns),
            "weights": {
                "vector": vector_weight,
                "lexical": round(lexical_weight, 3),
            },
            "results": shaped,
            "count": len(shaped),
            "observability": {"langfuse_enabled": observability.enabled()},
        }
    )


@app.get("/api/stats")
def stats() -> dict:
    """
    Counts per collection, plus a couple of narrative-relevant numbers.
    Useful as a defensible 'the database really has this data' endpoint.
    """
    try:
        counts = {}
        for name in config.ALL_OPERATIONAL_COLLECTIONS + config.ALL_MANAGED_COLLECTIONS:
            try:
                counts[name] = db.get_collection(name).estimated_document_count()
            except Exception:
                counts[name] = None
        # Namespace counts for memory_store
        mem = db.get_collection(config.COLL_MEMORY_STORE)
        guest_n = mem.count_documents({"namespace": list(config.GUEST_NAMESPACE)})
        fleet_n = mem.count_documents({"namespace": list(config.FLEET_NAMESPACE)})
        docs_n = mem.count_documents({"namespace": list(config.DOCS_NAMESPACE)})
        return {
            "database": config.MONGODB_DATABASE,
            "collection_counts": counts,
            "memory_namespaces": {
                "guests_fam_001": guest_n,
                "fleet_event_001": fleet_n,
                "docs_event_001": docs_n,
            },
        }
    except Exception as exc:  # noqa: BLE001
        log.exception("stats failed")
        raise HTTPException(500, f"Stats failed: {exc}") from exc


@app.get("/api/debug/embed")
def debug_embed(
    text: str = Query(..., min_length=1, description="Text to embed"),
    include_full: bool = Query(False, description="Include full vector in response"),
) -> dict:
    """
    Debug endpoint: embed a single string via Voyage and return vector stats.
    Used by the Vector Inspector panel in Tab 4.
    """
    try:
        t0 = time.time()
        vector = db.embed_text(text)
        elapsed_ms = round((time.time() - t0) * 1000, 1)

        norm = math.sqrt(sum(x * x for x in vector))

        result = {
            "text": text,
            "model": config.VOYAGE_MODEL,
            "dimensions": len(vector),
            "norm": round(norm, 4),
            "elapsed_ms": elapsed_ms,
            "first_10": vector[:10],
            "last_10": vector[-10:],
        }
        if include_full:
            result["full"] = vector
        return result
    except Exception as exc:
        log.exception("debug_embed failed")
        raise HTTPException(500, f"Embed failed: {exc}") from exc


@app.get("/api/debug/similarity")
def debug_similarity(
    a: str = Query(..., min_length=1, description="First string"),
    b: str = Query(..., min_length=1, description="Second string"),
) -> dict:
    """
    Debug endpoint: embed two strings and compute cosine similarity.
    Used by the Vector Inspector panel in Tab 4.
    """
    try:
        t0 = time.time()
        vec_a = db.embed_text(a)
        vec_b = db.embed_text(b)
        elapsed_ms = round((time.time() - t0) * 1000, 1)

        # Cosine similarity
        dot = sum(x * y for x, y in zip(vec_a, vec_b))
        norm_a = math.sqrt(sum(x * x for x in vec_a))
        norm_b = math.sqrt(sum(x * x for x in vec_b))
        cosine = dot / (norm_a * norm_b) if norm_a > 0 and norm_b > 0 else 0.0

        return {
            "a": a,
            "b": b,
            "model": config.VOYAGE_MODEL,
            "dimensions": len(vec_a),
            "cosine_similarity": round(cosine, 4),
            "elapsed_ms": elapsed_ms,
        }
    except Exception as exc:
        log.exception("debug_similarity failed")
        raise HTTPException(500, f"Similarity failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Unified Search endpoint
# ---------------------------------------------------------------------------


class UnifiedSearchRequest(BaseModel):
    """Request body for unified search across multiple namespaces."""

    query: str
    namespaces: list[str] = ["guests", "fleet", "docs"]
    limit_per: int = 3
    include_profile: bool = True  # Whether to join profile facts from guests collection


def _format_profile_fact(entry: dict) -> str:
    """Human-readable rendering of a profile fact for the UI."""
    name = entry["member_name"]
    role = entry["member_role"]
    flag = entry["flag"]

    flag_descriptions = {
        "peanut_allergy": f"{name} ({role}) has a confirmed peanut allergy. All dining recommendations must verify peanut-free preparation.",
        "nut_allergy": f"{name} ({role}) has a confirmed tree-nut allergy.",
        "dairy_allergy": f"{name} ({role}) has a confirmed dairy allergy.",
        "gluten_allergy": f"{name} ({role}) has a confirmed gluten intolerance.",
        "wheelchair_user": f"{name} ({role}) uses a wheelchair. Accessible routing required for all locations and venues.",
        "fatigue_risk": f"{name} ({role}) has elevated fatigue risk. Long queues and extended walking should be minimized.",
        "quiet_area_need": f"{name} ({role}) benefits from quiet areas for breaks and overstimulation recovery.",
        "coordinator": f"{name} ({role}) is the family's primary coordinator. Route booking confirmations and schedule updates to them.",
        "first_time_visitor": f"{name} ({role}) is a first-time visitor. Recommendations should be simple, explicit, and easy to follow.",
        "match_focused": f"{name} ({role}) is match-focused. Prioritize active courts and practice sessions over generic promotions.",
        "wayfinding_help": f"{name} ({role}) needs clear routing during schedule changes.",
        "premier_access": f"{name} ({role}) has premier access. Protect premium seating and hospitality continuity.",
        "covered_seating": f"{name} ({role}) prefers covered seating during weather risk.",
        "hospitality_priority": f"{name} ({role}) should receive proactive hospitality reservation protection.",
    }
    return flag_descriptions.get(flag, f"{name} ({role}) has flag: {flag}")


@app.post("/api/unified-search")
def unified_search(request: UnifiedSearchRequest) -> dict:
    """
    Search across multiple namespaces in one query. Returns a single ranked
    list mixing guest memories, fleet patterns, and visual documents, ordered
    by cosine score.

    Does NOT call Claude vision — that happens later if the user clicks on
    a visual document result to expand it.
    """
    query = request.query.strip()
    if not query:
        raise HTTPException(400, "query is required")

    # Build list of actual namespace tuples to search
    ns_map = {
        "guests": config.GUEST_NAMESPACE,
        "fleet": config.FLEET_NAMESPACE,
        "docs": config.DOCS_NAMESPACE,
    }
    to_search = [ns_map[k] for k in request.namespaces if k in ns_map]

    if not to_search:
        raise HTTPException(400, "At least one valid namespace required")

    try:
        t0 = time.time()
        query_vector = db.embed_text(query)
        embed_ms = round((time.time() - t0) * 1000, 1)

        # Run one $vectorSearch per namespace, then merge and re-rank by score
        coll = db.get_collection(config.COLL_MEMORY_STORE)
        all_results = []

        for ns in to_search:
            try:
                # Use namespace_str field (e.g., "guests_fam_001") for filtering
                # Atlas Vector Search filters only support scalar values, not arrays
                ns_str = "_".join(ns)
                pipeline = [
                    {
                        "$vectorSearch": {
                            "index": config.VECTOR_INDEX_NAME,
                            "path": "embedding",
                            "queryVector": query_vector,
                            "numCandidates": 20,
                            "limit": request.limit_per,
                            "filter": {"namespace_str": ns_str},
                        }
                    },
                    {
                        "$project": {
                            "_id": 0,
                            "key": 1,
                            "namespace": 1,
                            "value": 1,
                            "score": {"$meta": "vectorSearchScore"},
                        }
                    },
                ]
                results = list(coll.aggregate(pipeline))
                all_results.extend(results)
            except Exception as ns_exc:
                log.warning(f"Vector search failed for namespace {ns}: {ns_exc}")
                # Continue with other namespaces

        # Sort by score descending
        all_results.sort(key=lambda r: r.get("score", 0), reverse=True)

        search_ms = round((time.time() - t0) * 1000 - embed_ms, 1)

        # Shape for the frontend — include a kind discriminator
        shaped = []
        for r in all_results:
            ns = r.get("namespace", [])
            if ns == list(config.GUEST_NAMESPACE):
                kind = "guest_memory"
            elif ns == list(config.FLEET_NAMESPACE):
                kind = "fleet_pattern"
            elif ns == list(config.DOCS_NAMESPACE):
                kind = "visual_doc"
            else:
                kind = "unknown"

            val = r.get("value", {}) or {}

            # Build image_url for visual docs
            image_url = None
            if kind == "visual_doc":
                doc_type = val.get("doc_type", "")
                if doc_type:
                    image_url = f"/static/docs/{doc_type}.jpg"

            shaped.append(
                {
                    "kind": kind,
                    "key": r.get("key"),
                    "score": round(float(r.get("score", 0)), 3),
                    "text": val.get("text", ""),
                    "title": val.get("title"),
                    "category": val.get("category"),
                    "image_url": image_url,
                    "doc_type": val.get("doc_type"),
                    "visit_id": val.get("visit_id"),
                    "severity": val.get("severity"),
                }
            )

        # --- Structured profile-fact lookup (keyword-triggered join) ---
        profile_results = []
        profile_join_applied = False
        if request.include_profile:
            relevant_flags = db.flags_for_query(query)
            if relevant_flags:
                profile_join_applied = True
                all_entries = db.lookup_guest_flags(config.GUEST_ID)
                matching = [e for e in all_entries if e["flag"] in relevant_flags]
                for entry in matching:
                    profile_results.append({
                        "kind": "profile_fact",
                        "key": f"profile_{entry['member_id']}_{entry['flag']}",
                        "score": None,  # structured lookup has no cosine score
                        "text": _format_profile_fact(entry),
                        "member_name": entry["member_name"],
                        "member_role": entry["member_role"],
                        "flag": entry["flag"],
                    })

        # Merge: profile facts pinned to top, vector results ranked by score
        merged = profile_results + shaped

        return {
            "query": query,
            "namespaces_searched": [list(ns) for ns in to_search],
            "results": merged,
            "count": len(merged),
            "profile_join_applied": profile_join_applied,
            "timing": {
                "embed_ms": embed_ms,
                "search_ms": search_ms,
                "total_ms": round(embed_ms + search_ms, 1),
            },
        }

    except Exception as exc:
        log.exception("unified_search failed")
        raise HTTPException(500, f"Unified search failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Vision RAG endpoints
# ---------------------------------------------------------------------------


class VisionRAGRequest(BaseModel):
    """Request body for Vision RAG query."""

    query: str
    limit: int = 3


@app.get("/api/vision-rag/documents")
def list_visual_documents() -> dict:
    """
    List all visual documents in the docs namespace.
    Returns document keys, types, and text descriptions.
    """
    try:
        collection = db.get_collection(config.COLLECTION_MEMORY_STORE)
        docs = list(
            collection.find(
                {"namespace": list(config.DOCS_NAMESPACE)},
                {"_id": 0, "key": 1, "value": 1},
            )
        )

        documents = []
        for doc in docs:
            val = doc.get("value", {})
            documents.append(
                {
                    "key": doc.get("key", ""),
                    "doc_type": val.get("doc_type", ""),
                    "text": val.get("text", ""),
                    "category": val.get("category", ""),
                }
            )

        return {
            "namespace": list(config.DOCS_NAMESPACE),
            "count": len(documents),
            "documents": documents,
        }
    except Exception as exc:
        log.exception("list_visual_documents failed")
        raise HTTPException(500, f"Failed to list documents: {exc}") from exc


@app.post("/api/vision-rag/query")
def vision_rag_query(request: VisionRAGRequest) -> dict:
    """
    Vision RAG: text query → vector search → Claude vision reads image → answer.

    Flow:
    1. Embed query with voyage-multimodal-3.5
    2. Vector search over docs namespace to find relevant visual documents
    3. Load retrieved image(s) from disk
    4. Send to Claude vision model with the original query
    5. Return Claude's grounded answer
    """
    query = request.query.strip()
    if not query:
        raise HTTPException(400, "Query cannot be empty")

    try:
        t0 = time.time()

        # Step 1-2: Vector search over docs namespace
        results = db.vector_search(
            config.DOCS_NAMESPACE,
            query,
            limit=request.limit,
        )

        if not results:
            return {
                "query": query,
                "answer": "No relevant visual documents found for this query.",
                "sources": [],
                "elapsed_ms": round((time.time() - t0) * 1000, 1),
            }

        # Step 3: Load images from disk
        docs_dir = _STATIC_DIR / "docs"
        images_content = []
        sources = []

        for r in results:
            key = r.get("key", "")
            val = r.get("value", {})
            doc_type = val.get("doc_type", "")
            score = r.get("score", 0)

            # Map key to filename
            filename = f"{doc_type}.jpg"
            image_path = docs_dir / filename

            if image_path.exists():
                # Read and base64 encode for Claude
                image_bytes = image_path.read_bytes()
                image_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")

                images_content.append(
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": image_b64,
                        },
                    }
                )

                sources.append(
                    {
                        "key": key,
                        "doc_type": doc_type,
                        "score": round(score, 3),
                        "text": val.get("text", ""),
                    }
                )

        if not images_content:
            return {
                "query": query,
                "answer": "Found matching documents but could not load images.",
                "sources": sources,
                "elapsed_ms": round((time.time() - t0) * 1000, 1),
            }

        # Step 4: Send to Claude vision
        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

        # Build message content: images first, then the query
        content = images_content + [
            {
                "type": "text",
                "text": f"""Based on the operational document(s) shown above, please answer this question:

{query}

Provide a clear, concise answer grounded in what you can see in the document(s). If the document doesn't contain relevant information, say so.""",
            }
        ]

        response = client.messages.create(
            model=config.CLAUDE_VISION_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": content}],
        )

        answer = response.content[0].text if response.content else "No response generated."

        elapsed_ms = round((time.time() - t0) * 1000, 1)

        return {
            "query": query,
            "answer": answer,
            "sources": sources,
            "model": config.CLAUDE_VISION_MODEL,
            "elapsed_ms": elapsed_ms,
        }

    except anthropic.APIError as exc:
        log.exception("Claude API error in vision_rag_query")
        raise HTTPException(500, f"Claude API error: {exc}") from exc
    except Exception as exc:
        log.exception("vision_rag_query failed")
        raise HTTPException(500, f"Vision RAG query failed: {exc}") from exc


# Mount static AFTER the / route so index.html handler wins for root.
app.mount(
    "/static",
    StaticFiles(directory=str(_STATIC_DIR)),
    name="static",
)


def main() -> None:
    """Entrypoint for `python -m event_venue_operator.server`."""
    import os

    import uvicorn

    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(
        "event_venue_operator.server:app",
        host=host,
        port=port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
