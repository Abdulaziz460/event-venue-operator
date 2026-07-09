"""Project constants and environment configuration."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Final

from dotenv import load_dotenv

# Find the project root where .env lives.
_current = Path(__file__).resolve()
_project_root = _current.parent.parent.parent  # src/event_venue_operator/config.py -> project root
_env_file = _project_root / ".env"

if _env_file.exists():
    load_dotenv(_env_file)
else:
    load_dotenv()  # Fallback to default behavior


# ---------------------------------------------------------------------------
# LLM configuration
# ---------------------------------------------------------------------------

DEFAULT_MODEL: Final[str] = "claude-sonnet-4-6"
"""Default Claude model for plan and reflect nodes."""

FALLBACK_MODEL: Final[str] = "claude-opus-4-7"
"""Fallback Claude model if Sonnet reasoning quality is insufficient."""


# ---------------------------------------------------------------------------
# Embedding configuration
# ---------------------------------------------------------------------------

# voyage-multimodal-3.5 enables cross-modal search: text queries retrieve images
EMBEDDING_MODEL: Final[str] = "voyage-multimodal-3.5"
EMBEDDING_DIMENSIONS: Final[int] = 1024  # voyage-multimodal-3.5 default
EMBEDDING_SIMILARITY: Final[str] = "cosine"

# Claude vision model for reading retrieved documents
CLAUDE_VISION_MODEL: Final[str] = "claude-sonnet-4-5"


# ---------------------------------------------------------------------------
# MongoDB configuration
# ---------------------------------------------------------------------------

MONGODB_URI: Final[str] = os.environ.get("MONGODB_URI", "")
MONGODB_DATABASE: Final[str] = os.environ.get("MONGODB_DATABASE", "event_venue_operator")
MONGODB_APP_NAME: Final[str] = os.environ.get(
    "MONGODB_APP_NAME",
    "devrel-github-atlas-langgraph-marktechpost",
)

# Operational collections
COLLECTION_GUESTS: Final[str] = "guests"
COLLECTION_VISITS: Final[str] = "visits"
COLLECTION_VENUE_STATUS: Final[str] = "venue_status"
COLLECTION_OCCUPANCY_HISTORY: Final[str] = "occupancy_history"
COLLECTION_WEATHER_EVENTS: Final[str] = "weather_events"
COLLECTION_AGENT_ACTIONS: Final[str] = "agent_actions"
COLLECTION_VENUES: Final[str] = "venues"
COLLECTION_RESERVATIONS: Final[str] = "reservations"
COLLECTION_EVENT_METRICS: Final[str] = "event_metrics"

# LangGraph-managed collections
COLLECTION_CHECKPOINTS: Final[str] = "checkpoints"
COLLECTION_CHECKPOINT_WRITES: Final[str] = "checkpoint_writes"
COLLECTION_MEMORY_STORE: Final[str] = "memory_store"

VECTOR_INDEX_NAME: Final[str] = "memory_store_vector_index"

# Collection groupings (for setup scripts)
ALL_OPERATIONAL_COLLECTIONS: Final[list[str]] = [
    COLLECTION_GUESTS,
    COLLECTION_VISITS,
    COLLECTION_VENUE_STATUS,
    COLLECTION_OCCUPANCY_HISTORY,
    COLLECTION_WEATHER_EVENTS,
    COLLECTION_VENUES,
    COLLECTION_RESERVATIONS,
    COLLECTION_AGENT_ACTIONS,
    COLLECTION_EVENT_METRICS,
]

ALL_MANAGED_COLLECTIONS: Final[list[str]] = [
    COLLECTION_MEMORY_STORE,
    COLLECTION_CHECKPOINTS,
    COLLECTION_CHECKPOINT_WRITES,
]

# Short aliases for server.py compatibility
COLL_MEMORY_STORE: Final[str] = COLLECTION_MEMORY_STORE
COLL_GUESTS: Final[str] = COLLECTION_GUESTS
COLL_VISITS: Final[str] = COLLECTION_VISITS
COLL_VENUE_STATUS: Final[str] = COLLECTION_VENUE_STATUS
COLL_OCCUPANCY_HISTORY: Final[str] = COLLECTION_OCCUPANCY_HISTORY
COLL_WEATHER: Final[str] = COLLECTION_WEATHER_EVENTS
COLL_VENUES: Final[str] = COLLECTION_VENUES
COLL_RESERVATIONS: Final[str] = COLLECTION_RESERVATIONS
COLL_AGENT_ACTIONS: Final[str] = COLLECTION_AGENT_ACTIONS
COLL_EVENT_METRICS: Final[str] = COLLECTION_EVENT_METRICS
COLL_CHECKPOINTS: Final[str] = COLLECTION_CHECKPOINTS
COLL_CHECKPOINT_WRITES: Final[str] = COLLECTION_CHECKPOINT_WRITES


# ---------------------------------------------------------------------------
# Memory namespace prefixes
# ---------------------------------------------------------------------------

NAMESPACE_GUESTS: Final[str] = "guests"
NAMESPACE_FLEET: Final[str] = "fleet"
NAMESPACE_DOCS: Final[str] = "docs"


# ---------------------------------------------------------------------------
# Memory entry categories
# ---------------------------------------------------------------------------
# Every entry written to MongoDBStore carries one of these category tags.
# Memory store entries use a stable value schema shared by seed and graph code.

MEMORY_CATEGORIES: Final[frozenset[str]] = frozenset({
    "venue_incident",
    "court_delay",
    "first_timer_navigation",
    "weather_incident",
    "accessibility_fatigue",
    "missed_reservation",
    "preference",
    "behavior_pattern",
    "satisfaction_low",
    "experience_gap",
    "visual_document",
})

MEMORY_SEVERITIES: Final[frozenset[str]] = frozenset({"low", "medium", "high"})


# ---------------------------------------------------------------------------
# Fictional event-location roster
# ---------------------------------------------------------------------------

VENUE_LOCATIONS: Final[dict[str, str]] = {
    "centre_court": "Centre Court",
    "court_1": "Court 1",
    "court_2": "Court 2",
    "covered_practice_court": "Covered Practice Court",
    "champions_lounge": "Champions Lounge",
    "food_village": "Food Village",
}


# ---------------------------------------------------------------------------
# Demo identifiers
# ---------------------------------------------------------------------------

DEMO_GUEST_ID: Final[str] = "fam_001"
DEMO_EVENT_ID: Final[str] = "event_001"
VISIT_3_ID: Final[str] = "visit_3"

# Namespace tuples for MongoDBStore / vector search
GUEST_NAMESPACE: Final[tuple[str, str]] = (NAMESPACE_GUESTS, DEMO_GUEST_ID)
FLEET_NAMESPACE: Final[tuple[str, str]] = (NAMESPACE_FLEET, DEMO_EVENT_ID)
DOCS_NAMESPACE: Final[tuple[str, str]] = (NAMESPACE_DOCS, DEMO_EVENT_ID)

# Short aliases for UI compatibility
GUEST_ID: Final[str] = DEMO_GUEST_ID
EVENT_ID: Final[str] = DEMO_EVENT_ID

# Embedding aliases for server.py compatibility
VOYAGE_MODEL: Final[str] = EMBEDDING_MODEL
EMBED_DIMS: Final[int] = EMBEDDING_DIMENSIONS


# ---------------------------------------------------------------------------
# API keys (from environment)
# ---------------------------------------------------------------------------

ANTHROPIC_API_KEY: Final[str] = os.environ.get("ANTHROPIC_API_KEY", "")
VOYAGE_API_KEY: Final[str] = os.environ.get("VOYAGE_API_KEY", "") or os.environ.get("VOYAGE_AI_API_KEY", "")

LANGFUSE_PUBLIC_KEY: Final[str] = os.environ.get("LANGFUSE_PUBLIC_KEY", "")
LANGFUSE_SECRET_KEY: Final[str] = os.environ.get("LANGFUSE_SECRET_KEY", "")
LANGFUSE_HOST: Final[str] = os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com")

LANGFUSE_ENABLED: Final[bool] = bool(LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY)


def validate_env(required: list[str]) -> None:
    """Raise if any required environment variable is missing.

    Call this at startup in scripts/ entry points. Fails fast and loud rather
    than letting a missing key surface deep in a tool call.
    """
    missing: list[str] = [key for key in required if not os.environ.get(key)]

    if missing:
        msg = (
            f"Missing required environment variables: {', '.join(missing)}. "
            "Copy .env.example to .env and fill them in."
        )
        raise RuntimeError(msg)


def validate_required_env() -> None:
    """Raise if the full-stack environment is incomplete."""
    validate_env(["MONGODB_URI", "ANTHROPIC_API_KEY", "VOYAGE_API_KEY"])
