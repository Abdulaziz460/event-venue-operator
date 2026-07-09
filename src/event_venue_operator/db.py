"""MongoDB client, checkpointer, and store setup.

This module provides factory functions for all MongoDB-related resources:
- PyMongo client and database access
- MongoDBSaver for LangGraph session state checkpointing
- MongoDBStore for semantic memory with vector search
- VoyageAI embeddings

All operational writes (to guests, visits, venue_status, etc.) should go through
typed helpers in this module. Do not scatter pymongo calls across nodes.
"""

from __future__ import annotations

import re
from contextlib import contextmanager
from functools import lru_cache
from typing import TYPE_CHECKING, Any, Iterable, Iterator
from urllib.parse import parse_qsl, urlencode

import voyageai
from langchain_core.embeddings import Embeddings
from langgraph.checkpoint.mongodb import MongoDBSaver
from langgraph.store.mongodb import MongoDBStore, create_vector_index_config
from pymongo import MongoClient
from pymongo.database import Database

from event_venue_operator import config


# ---------------------------------------------------------------------------
# Custom multimodal embeddings for LangChain/LangGraph integration
# ---------------------------------------------------------------------------


class VoyageMultimodalEmbeddings(Embeddings):
    """Custom embeddings class using voyage-multimodal-3.5.

    The standard VoyageAIEmbeddings uses voyage.embed() which doesn't support
    multimodal models. This class uses voyage.multimodal_embed() instead,
    enabling cross-modal search where text queries can retrieve images.
    """

    def __init__(self, api_key: str | None = None):
        self._client = voyageai.Client(api_key=api_key or config.VOYAGE_API_KEY)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of documents."""
        if not texts:
            return []
        inputs = [[t] for t in texts]
        result = self._client.multimodal_embed(
            inputs=inputs,
            model=config.VOYAGE_MODEL,
            input_type="document",
            output_dimension=config.EMBED_DIMS,
        )
        return result.embeddings

    def embed_query(self, text: str) -> list[float]:
        """Embed a single query."""
        result = self._client.multimodal_embed(
            inputs=[[text]],
            model=config.VOYAGE_MODEL,
            input_type="query",
            output_dimension=config.EMBED_DIMS,
        )
        return result.embeddings[0]


if TYPE_CHECKING:
    from pymongo.collection import Collection


# ---------------------------------------------------------------------------
# MongoDB client and database
# ---------------------------------------------------------------------------


def _conn_string_with_app_name(uri: str) -> str:
    """Return a MongoDB URI with the configured appName query parameter."""
    base, sep, query = uri.partition("?")
    params = [
        (key, value)
        for key, value in parse_qsl(query, keep_blank_values=True)
        if key.lower() != "appname"
    ]
    params.append(("appName", config.MONGODB_APP_NAME))
    return f"{base}{sep or '?'}{urlencode(params)}"


@lru_cache(maxsize=1)
def get_mongo_client() -> MongoClient:
    """Return a cached MongoClient instance.

    The client is created once and reused across the application lifetime.
    Connection string comes from MONGODB_URI environment variable.
    """
    if not config.MONGODB_URI:
        raise RuntimeError(
            "MONGODB_URI not set. Copy .env.example to .env and populate it."
        )
    return MongoClient(config.MONGODB_URI, appname=config.MONGODB_APP_NAME)


def get_database() -> Database:
    """Return the event_venue_operator database instance."""
    return get_mongo_client()[config.MONGODB_DATABASE]


def get_collection(name: str) -> Collection:
    """Return a collection by name from the event_venue_operator database."""
    return get_database()[name]


# ---------------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def get_embeddings() -> VoyageMultimodalEmbeddings:
    """Return a cached VoyageMultimodalEmbeddings instance.

    Uses voyage-multimodal-3.5 model with 1024 dimensions. This enables
    cross-modal search where text queries can retrieve image documents.
    """
    if not config.VOYAGE_API_KEY:
        raise RuntimeError(
            "VOYAGE_API_KEY not set. Copy .env.example to .env and populate it."
        )
    return VoyageMultimodalEmbeddings(api_key=config.VOYAGE_API_KEY)


# ---------------------------------------------------------------------------
# LangGraph checkpointer (session state)
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def get_checkpointer() -> MongoDBSaver:
    """Return a cached MongoDBSaver instance for session state checkpointing.

    Thread-scoped by visit_id. Each visit gets a unique thread ID, and the
    agent's full session state persists as checkpoints.

    Collections used: checkpoints, checkpoint_writes
    """
    client = get_mongo_client()
    return MongoDBSaver(
        client,
        db_name=config.MONGODB_DATABASE,
    )


# ---------------------------------------------------------------------------
# LangGraph store (semantic memory)
# ---------------------------------------------------------------------------


def _get_vector_index_config():
    """Create the vector index config for MongoDBStore."""
    return create_vector_index_config(
        dims=config.EMBEDDING_DIMENSIONS,
        embed=get_embeddings(),
        name=config.VECTOR_INDEX_NAME,
        relevance_score_fn="cosine",
    )


@contextmanager
def get_store() -> Iterator[MongoDBStore]:
    """Return a MongoDBStore instance for semantic memory as a context manager.

    Usage:
        with get_store() as store:
            store.put(namespace, key, value)
            results = store.search(namespace, query)

    Configured with vector search using Voyage embeddings. Namespace structure:
    - ("guests", guest_id) for per-guest semantic memory
    - ("fleet", event_id) for operator-level patterns

    The backing collection needs a vector search index created via
    scripts/setup_atlas.py before use.
    """
    with MongoDBStore.from_conn_string(
        conn_string=_conn_string_with_app_name(config.MONGODB_URI),
        db_name=config.MONGODB_DATABASE,
        collection_name=config.COLLECTION_MEMORY_STORE,
        index_config=_get_vector_index_config(),
    ) as store:
        yield store


def get_store_for_graph() -> Iterator[MongoDBStore]:
    """Return the store factory for LangGraph graph compilation.

    LangGraph's compile() expects a store factory (callable returning context manager).
    Pass this function directly to compile(store=get_store_for_graph).
    """
    return MongoDBStore.from_conn_string(
        conn_string=_conn_string_with_app_name(config.MONGODB_URI),
        db_name=config.MONGODB_DATABASE,
        collection_name=config.COLLECTION_MEMORY_STORE,
        index_config=_get_vector_index_config(),
    )


# ---------------------------------------------------------------------------
# Operational data helpers
# ---------------------------------------------------------------------------


def get_guest(guest_id: str) -> dict | None:
    """Retrieve a guest profile by ID."""
    return get_collection(config.COLLECTION_GUESTS).find_one({"guest_id": guest_id})


def lookup_guest_flags(guest_id: str) -> list[dict]:
    """Return a flat list of profile-fact entries for a guest's party members.

    Structured lookup, no vector search. Used by /api/unified-search when
    the query touches flag-relevant territory.

    Returns entries shaped like:
        {
            "member_id": "nina",
            "member_name": "Nina",
            "member_role": "premier_guest",
            "flag": "covered_seating",
        }
    """
    coll = get_collection(config.COLLECTION_GUESTS)
    doc = coll.find_one({"guest_id": guest_id}, {"_id": 0, "members": 1})
    if not doc:
        return []

    entries = []
    for member in doc.get("members", []):
        for flag in member.get("flags", []):
            entries.append({
                "member_id": member.get("member_id"),
                "member_name": member.get("name"),
                "member_role": member.get("role"),
                "flag": flag,
            })
    return entries


# ---------------------------------------------------------------------------
# Keyword-to-flag relevance mapping
# ---------------------------------------------------------------------------

# Keywords → which flags they should surface
FLAG_KEYWORD_MAP: dict[str, list[str]] = {
    # Allergies / dietary
    "allergy": ["peanut_allergy", "nut_allergy", "dairy_allergy", "gluten_allergy"],
    "allergies": ["peanut_allergy", "nut_allergy", "dairy_allergy", "gluten_allergy"],
    "dietary": ["peanut_allergy", "nut_allergy", "dairy_allergy", "gluten_allergy"],
    "peanut": ["peanut_allergy"],
    "food": ["peanut_allergy", "nut_allergy", "dairy_allergy", "gluten_allergy"],

    # Accessibility / mobility
    "accessibility": ["wheelchair_user", "fatigue_risk", "quiet_area_need"],
    "accessible": ["wheelchair_user", "fatigue_risk"],
    "mobility": ["wheelchair_user", "fatigue_risk"],
    "wheelchair": ["wheelchair_user"],
    "fatigue": ["fatigue_risk"],
    "quiet": ["quiet_area_need"],

    # Preferences
    "first": ["first_time_visitor", "wayfinding_help"],
    "first-time": ["first_time_visitor", "wayfinding_help"],
    "match": ["match_focused"],
    "wayfinding": ["wayfinding_help"],
    "premier": ["premier_access", "hospitality_priority"],
    "covered": ["covered_seating"],
    "hospitality": ["hospitality_priority"],
}


def flags_for_query(query: str) -> set[str]:
    """Given a search query, return the set of profile flags that are relevant.

    Case-insensitive substring match against the keyword map.
    """
    query_lower = query.lower()
    relevant: set[str] = set()
    for keyword, flags in FLAG_KEYWORD_MAP.items():
        if keyword in query_lower:
            relevant.update(flags)
    return relevant


def get_visit(visit_id: str) -> dict | None:
    """Retrieve a visit document by ID."""
    return get_collection(config.COLLECTION_VISITS).find_one({"visit_id": visit_id})


def get_current_venue_status() -> list[dict]:
    """Retrieve current status for all event locations.

    Excludes the MongoDB _id field to ensure JSON serialization works.
    """
    return list(get_collection(config.COLLECTION_VENUE_STATUS).find({}, {"_id": 0}))


def upsert_visit(visit: dict) -> None:
    """Insert or update a visit document."""
    get_collection(config.COLLECTION_VISITS).update_one(
        {"visit_id": visit["visit_id"]},
        {"$set": visit},
        upsert=True,
    )


def log_agent_action(action: dict) -> None:
    """Log an agent action to the agent_actions collection."""
    get_collection(config.COLLECTION_AGENT_ACTIONS).insert_one(action)


def update_venue_status(location_id: str, status: str, wait_minutes: int | None = None) -> dict:
    """Update the status of a venue location.

    Args:
        location_id: The venue location identifier (e.g., "centre_court")
        status: The new status ("operational", "closed", "reduced_capacity")
        wait_minutes: Optional wait time in minutes

    Returns:
        The updated venue status document
    """
    from datetime import datetime, timezone

    update = {
        "location_id": location_id,
        "status": status,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if wait_minutes is not None:
        update["current_wait_minutes"] = wait_minutes

    get_collection(config.COLLECTION_VENUE_STATUS).update_one(
        {"location_id": location_id},
        {"$set": update},
        upsert=True,
    )
    return update


def clear_visit(visit_id: str) -> None:
    """Clear a visit document (for demo reset)."""
    get_collection(config.COLLECTION_VISITS).delete_one({"visit_id": visit_id})


def get_active_weather_event() -> dict | None:
    """Get the current active weather event, if any."""
    return get_collection(config.COLLECTION_WEATHER_EVENTS).find_one(
        {"status": "active"},
        {"_id": 0},
        sort=[("created_at", -1)],
    )


def create_weather_event(
    event_type: str,
    severity: str,
    forecast_hours: float = 2.0,
) -> dict:
    """Create a weather event (e.g., thunderstorm forecast).

    Args:
        event_type: Type of weather event ("thunderstorm", "heat_advisory", etc.)
        severity: Severity level ("low", "medium", "high")
        forecast_hours: Hours until the event is expected

    Returns:
        The created weather event document
    """
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    event = {
        "event_type": event_type,
        "severity": severity,
        "status": "active",
        "forecast_for": (now + timedelta(hours=forecast_hours)).isoformat(),
        "created_at": now.isoformat(),
        "event_id": config.DEMO_EVENT_ID,
    }

    get_collection(config.COLLECTION_WEATHER_EVENTS).insert_one(event)
    # Return without _id for JSON serialization
    return {k: v for k, v in event.items() if k != "_id"}


def clear_weather_events() -> None:
    """Clear all active weather events (mark as resolved)."""
    from datetime import datetime, timezone

    get_collection(config.COLLECTION_WEATHER_EVENTS).update_many(
        {"status": "active"},
        {
            "$set": {
                "status": "resolved",
                "resolved_at": datetime.now(timezone.utc).isoformat(),
            }
        },
    )


def init_venue_status() -> None:
    """Initialize the status collection with default event-venue locations."""
    from datetime import datetime, timezone

    locations = [
        {"location_id": "centre_court", "name": "Centre Court", "current_wait_minutes": 18},
        {"location_id": "court_1", "name": "Court 1", "current_wait_minutes": 22},
        {"location_id": "court_2", "name": "Court 2", "current_wait_minutes": 35},
        {"location_id": "covered_practice_court", "name": "Covered Practice Court", "current_wait_minutes": 10},
        {"location_id": "champions_lounge", "name": "Champions Lounge", "current_wait_minutes": 8},
        {"location_id": "food_village", "name": "Food Village", "current_wait_minutes": 12},
    ]

    collection = get_collection(config.COLLECTION_VENUE_STATUS)
    collection.delete_many({})

    for location in locations:
        collection.update_one(
            {"location_id": location["location_id"]},
            {
                "$set": {
                    "location_id": location["location_id"],
                    "name": location["name"],
                    "status": "operational",
                    "current_wait_minutes": location["current_wait_minutes"],
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            },
            upsert=True,
        )


# ---------------------------------------------------------------------------
# Direct Voyage SDK helpers (for server.py and UI vector search)
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def get_voyage() -> voyageai.Client:
    """Return a cached Voyage AI client instance.

    Uses direct SDK for embedding operations in the server layer.
    For LangGraph integration, use get_embeddings() instead.
    """
    if not config.VOYAGE_API_KEY:
        raise RuntimeError(
            "VOYAGE_API_KEY not set. Copy .env.example to .env and populate it."
        )
    return voyageai.Client(api_key=config.VOYAGE_API_KEY)


def embed_text(text: str) -> list[float]:
    """Embed a single text string via voyage-multimodal-3.5.

    Uses input_type="query" for search queries. Returns 1024-dim vector.
    Uses multimodal_embed so text queries can find image documents.
    """
    voyage = get_voyage()
    # multimodal_embed takes List[List[content_items]]
    result = voyage.multimodal_embed(
        inputs=[[text]],
        model=config.VOYAGE_MODEL,
        input_type="query",
        output_dimension=config.EMBED_DIMS,
    )
    return result.embeddings[0]


def embed_documents(texts: Iterable[str]) -> list[list[float]]:
    """Batch embed multiple text documents.

    Uses input_type="document" for indexing. Returns list of 1024-dim vectors.
    Uses multimodal_embed so all embeddings live in the same cross-modal space.
    """
    voyage = get_voyage()
    texts = list(texts)
    if not texts:
        return []
    # Each text becomes a single-element list
    inputs = [[t] for t in texts]
    result = voyage.multimodal_embed(
        inputs=inputs,
        model=config.VOYAGE_MODEL,
        input_type="document",
        output_dimension=config.EMBED_DIMS,
    )
    return result.embeddings


def embed_image_from_bytes(image_bytes: bytes) -> list[float]:
    """Embed an image via voyage-multimodal-3.5. Returns 1024-dim vector.

    Converts bytes to PIL Image and passes to multimodal_embed.
    Uses input_type="document" for indexing stored images.
    """
    from io import BytesIO

    from PIL import Image

    voyage = get_voyage()
    img = Image.open(BytesIO(image_bytes)).convert("RGB")

    result = voyage.multimodal_embed(
        inputs=[[img]],
        model=config.VOYAGE_MODEL,
        input_type="document",
        output_dimension=config.EMBED_DIMS,
    )
    embedding = result.embeddings[0]

    # Sanity check dimensions
    if len(embedding) != config.EMBED_DIMS:
        raise ValueError(f"Expected {config.EMBED_DIMS} dims, got {len(embedding)}")
    return embedding


def embed_image_from_path(path) -> list[float]:
    """Convenience wrapper to embed an image from disk."""
    from pathlib import Path
    return embed_image_from_bytes(Path(path).read_bytes())


def vector_search(
    namespace: tuple[str, str],
    query_text: str,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Real Atlas Vector Search over the memory_store collection.

    Scoped by namespace. Returns a list of results with score + memory metadata.
    This is the function the /api/search endpoint calls.

    Args:
        namespace: Tuple like ("guests", "fam_001") or ("fleet", "event_001")
        query_text: The search query to embed and search
        limit: Maximum number of results

    Returns:
        List of dicts with key, namespace, value, and score
    """
    query_vector = embed_text(query_text)
    coll = get_collection(config.COLL_MEMORY_STORE)

    namespace_str = "_".join(namespace)

    pipeline = [
        {
            "$vectorSearch": {
                "index": config.VECTOR_INDEX_NAME,
                "path": "embedding",
                "queryVector": query_vector,
                "numCandidates": 50,
                "limit": limit,
                "filter": {"namespace_str": namespace_str},
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

    return list(coll.aggregate(pipeline))


def hybrid_search(
    namespace: tuple[str, str],
    query_text: str,
    limit: int = 5,
    vector_weight: float = 0.7,
    lexical_weight: float = 0.3,
) -> list[dict[str, Any]]:
    """Hybrid retrieval over memory_store.

    This combines Atlas Vector Search with a deterministic lexical score over
    memory text. It works with the existing vector index and seeded data, so
    readers do not need to create a second Atlas Search text index for v1.
    """
    vector_results = vector_search(namespace, query_text, limit=max(limit, 10))
    namespace_str = "_".join(namespace)
    coll = get_collection(config.COLL_MEMORY_STORE)

    query_terms = [
        term
        for term in re.findall(r"[a-z0-9]+", query_text.lower())
        if len(term) > 2
    ][:8]

    lexical_filter: dict[str, Any] = {"namespace_str": namespace_str}
    lexical_docs: list[dict[str, Any]] = []
    if query_terms:
        lexical_filter["value.text"] = {
            "$regex": "|".join(re.escape(term) for term in query_terms),
            "$options": "i",
        }
        lexical_docs = list(
            coll.find(
                lexical_filter,
                {"_id": 0, "key": 1, "namespace": 1, "value": 1},
            ).limit(50)
        )

    merged: dict[str, dict[str, Any]] = {}
    max_vector_score = max((float(r.get("score", 0)) for r in vector_results), default=1.0)
    if max_vector_score <= 0:
        max_vector_score = 1.0

    for result in vector_results:
        key = result.get("key", "")
        vector_score = float(result.get("score", 0))
        merged[key] = {
            **result,
            "vector_score": vector_score,
            "vector_score_normalized": vector_score / max_vector_score,
            "lexical_score": 0.0,
            "lexical_matches": [],
        }

    for doc in lexical_docs:
        key = doc.get("key", "")
        text = ((doc.get("value", {}) or {}).get("text", "")).lower()
        matches = sorted({term for term in query_terms if term in text})
        lexical_score = len(matches) / len(query_terms) if query_terms else 0.0

        if key not in merged:
            merged[key] = {
                **doc,
                "score": 0.0,
                "vector_score": 0.0,
                "vector_score_normalized": 0.0,
                "lexical_score": lexical_score,
                "lexical_matches": matches,
            }
        else:
            merged[key]["lexical_score"] = lexical_score
            merged[key]["lexical_matches"] = matches

    for item in merged.values():
        item["hybrid_score"] = (
            vector_weight * item["vector_score_normalized"]
            + lexical_weight * item["lexical_score"]
        )

    ranked = sorted(merged.values(), key=lambda r: r.get("hybrid_score", 0), reverse=True)
    return ranked[:limit]


def ping() -> bool:
    """Verify the MongoDB connection is alive."""
    try:
        get_mongo_client().admin.command("ping")
        return True
    except Exception:
        return False


# Alias for server.py compatibility (uses get_db instead of get_database)
get_db = get_database
