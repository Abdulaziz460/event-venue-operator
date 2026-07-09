#!/usr/bin/env python3
"""Seed visual documents into the docs namespace for Vision RAG.

Embeds each image using voyage-multimodal-3.5 and stores in memory_store
with the same schema MongoDBStore uses.

Run:
    uv run python scripts/seed_visual_docs.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console

# Add src to path for imports
sys.path.insert(0, "src")

from event_venue_operator import config
from event_venue_operator.db import (
    embed_image_from_path,
    get_collection,
)

console = Console()

DOCS_DIR = Path(__file__).resolve().parents[1] / "static" / "docs"

# Visual document definitions with descriptive metadata
VISUAL_DOCUMENTS = [
    {
        "key": "visual_allergen_matrix",
        "file": "allergen_matrix.jpg",
        "value": {
            "text": "Premier Tennis dining allergen accommodation matrix showing peanut-free, tree nut-free, gluten-free, dairy-free, and shellfish-free options at Baseline Cafe, Champions Dining, Premier Club, Food Village, Garden Pavilion, and Rooftop Terrace",
            "category": "visual_document",
            "doc_type": "allergen_matrix",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    },
    {
        "key": "visual_accessibility_map",
        "file": "accessibility_map.jpg",
        "value": {
            "text": "Premier Tennis covered and accessible route map showing rain-delay paths between Main Gate, Centre Court, Court 1, Court 2, Covered Practice Court, Food Village, Champions Lounge, and Medical and Information",
            "category": "visual_document",
            "doc_type": "accessibility_map",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    },
    {
        "key": "visual_height_requirements",
        "file": "height_requirements.jpg",
        "value": {
            "text": "Covered hospitality and shelter capacity chart showing available rain-delay capacity at Champions Lounge, Premier Club, Covered Practice Court, Baseline Cafe, Garden Pavilion, and Food Village",
            "category": "visual_document",
            "doc_type": "hospitality_capacity",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    },
    {
        "key": "visual_weather_response",
        "file": "weather_response.jpg",
        "value": {
            "text": "Rain delay response protocol flowchart showing forecast detection, Mikiko first-timer routing, Nina premier hospitality protection, covered movement, and memory write-back",
            "category": "visual_document",
            "doc_type": "weather_response",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    },
    {
        "key": "visual_evacuation_zones",
        "file": "evacuation_zones.jpg",
        "value": {
            "text": "Premier Tennis evacuation and shelter zones showing Centre Court, Court 1, Court 2, Food Village, hospitality suites, practice courts, signed gates, and lightning-risk shelter instructions",
            "category": "visual_document",
            "doc_type": "evacuation_zones",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    },
]


def seed_visual_documents() -> None:
    """Seed visual documents into the docs namespace.

    Computes image embeddings using voyage-multimodal-3.5 and writes
    directly to memory_store collection with MongoDBStore-compatible schema.
    """
    namespace = config.DOCS_NAMESPACE  # ("docs", "event_001")
    namespace_str = "_".join(namespace)

    console.print(f"\n[bold]Seeding visual documents into namespace:[/bold] {namespace}\n")

    collection = get_collection(config.COLLECTION_MEMORY_STORE)
    collection.delete_many(
        {
            "key": {"$in": [doc["key"] for doc in VISUAL_DOCUMENTS]},
            "namespace": list(namespace),
        }
    )

    for doc in VISUAL_DOCUMENTS:
        image_path = DOCS_DIR / doc["file"]

        if not image_path.exists():
            console.print(f"  [red]Missing:[/red] {image_path}")
            continue

        console.print(f"  [dim]Embedding:[/dim] {doc['file']}...")

        # Compute image embedding
        embedding = embed_image_from_path(image_path)

        # Store with MongoDBStore-compatible schema
        # MongoDBStore uses: namespace, key, value, embedding, created_at, updated_at
        store_doc = {
            "namespace": list(namespace),  # MongoDBStore stores as array
            "namespace_str": namespace_str,  # For direct vector search filtering
            "key": doc["key"],
            "value": doc["value"],
            "embedding": embedding,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }

        # Upsert by key
        collection.update_one(
            {"namespace": list(namespace), "key": doc["key"]},
            {"$set": store_doc},
            upsert=True,
        )

        console.print(f"  [green]Stored:[/green] {doc['key']}")

    console.print(f"\n[bold green]Seeded {len(VISUAL_DOCUMENTS)} visual documents[/bold green]\n")


def verify_visual_documents() -> None:
    """Verify visual documents are searchable."""
    from event_venue_operator.db import vector_search

    console.print("\n[bold]Verifying visual document search:[/bold]\n")

    test_queries = [
        ("peanut allergy dining", "docs"),
        ("covered accessible routes", "docs"),
        ("premier hospitality capacity", "docs"),
        ("rain delay protocol", "docs"),
        ("emergency evacuation", "docs"),
    ]

    for query, ns_prefix in test_queries:
        namespace = (ns_prefix, config.DEMO_EVENT_ID)
        results = vector_search(namespace, query, limit=1)

        if results:
            top = results[0]
            console.print(f"  [cyan]Query:[/cyan] \"{query}\"")
            console.print(f"    [green]Top match:[/green] {top['key']} (score: {top['score']:.3f})")
        else:
            console.print(f"  [cyan]Query:[/cyan] \"{query}\"")
            console.print(f"    [yellow]No results[/yellow]")


def main():
    """Seed and verify visual documents."""
    config.validate_required_env()

    seed_visual_documents()
    verify_visual_documents()


if __name__ == "__main__":
    main()
