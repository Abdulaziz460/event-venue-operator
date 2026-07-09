#!/usr/bin/env python3
"""One-time Atlas setup: create collections and vector search index.

Run this once before seeding data:

    uv run python scripts/setup_atlas.py

The vector search index takes ~15-30 seconds to build after creation.
Wait for it to complete before running seed_data.py.
"""

from __future__ import annotations

import sys
import time

from pymongo.operations import SearchIndexModel
from rich.console import Console

# Add src to path for imports
sys.path.insert(0, "src")

from event_venue_operator import config
from event_venue_operator.db import get_database

console = Console()


def create_collections() -> None:
    """Create operational collections if they don't exist."""
    db = get_database()
    existing = set(db.list_collection_names())

    collections_to_create = [
        name
        for name in config.ALL_OPERATIONAL_COLLECTIONS + config.ALL_MANAGED_COLLECTIONS
        if name != config.COLLECTION_OCCUPANCY_HISTORY
    ]

    for coll_name in collections_to_create:
        if coll_name not in existing:
            db.create_collection(coll_name)
            console.print(f"  [green]Created collection:[/green] {coll_name}")
        else:
            console.print(f"  [dim]Already exists:[/dim] {coll_name}")

    # Create time series collection for occupancy and queue history
    if config.COLLECTION_OCCUPANCY_HISTORY not in existing:
        db.create_collection(
            config.COLLECTION_OCCUPANCY_HISTORY,
            timeseries={
                "timeField": "timestamp",
                "metaField": "location_id",
                "granularity": "minutes",
            },
        )
        console.print(
            f"  [green]Created time series collection:[/green] "
            f"{config.COLLECTION_OCCUPANCY_HISTORY}"
        )
    else:
        console.print(
            f"  [dim]Already exists:[/dim] {config.COLLECTION_OCCUPANCY_HISTORY}"
        )


def delete_vector_search_index() -> bool:
    """Delete the existing vector search index if it exists."""
    db = get_database()
    collection = db[config.COLLECTION_MEMORY_STORE]

    existing_indexes = list(collection.list_search_indexes())
    for idx in existing_indexes:
        if idx.get("name") == config.VECTOR_INDEX_NAME:
            console.print(f"  [yellow]Deleting existing index:[/yellow] {config.VECTOR_INDEX_NAME}")
            collection.drop_search_index(config.VECTOR_INDEX_NAME)
            return True
    return False


def create_vector_search_index() -> None:
    """Create the vector search index on the memory_store collection.

    MongoDBStore uses these fields:
    - embedding: vector field (1024 dimensions, cosine similarity)
    - namespace_prefix: filter field for namespace queries
    - value.visit_id: filter field for visit-specific queries
    """
    db = get_database()
    collection = db[config.COLLECTION_MEMORY_STORE]

    # Check if index already exists
    existing_indexes = list(collection.list_search_indexes())
    existing_names = {idx.get("name") for idx in existing_indexes}

    if config.VECTOR_INDEX_NAME in existing_names:
        console.print(
            f"  [dim]Vector index already exists:[/dim] {config.VECTOR_INDEX_NAME}"
        )
        return

    # Create the vector search index
    # MongoDBStore uses "namespace_prefix" for filtering
    # API endpoints use "namespace_str" for filtering direct Atlas Vector Search
    search_index_model = SearchIndexModel(
        definition={
            "fields": [
                {
                    "type": "vector",
                    "path": "embedding",
                    "numDimensions": config.EMBEDDING_DIMENSIONS,
                    "similarity": config.EMBEDDING_SIMILARITY,
                },
                {"type": "filter", "path": "namespace_prefix"},
                {"type": "filter", "path": "namespace_str"},
                {"type": "filter", "path": "value.visit_id"},
            ]
        },
        name=config.VECTOR_INDEX_NAME,
        type="vectorSearch",
    )

    console.print(f"  [yellow]Creating vector search index:[/yellow] {config.VECTOR_INDEX_NAME}")
    collection.create_search_index(model=search_index_model)
    console.print(f"  [green]Index creation initiated.[/green]")


def wait_for_index_ready(timeout_seconds: int = 60) -> bool:
    """Wait for the vector search index to be ready."""
    db = get_database()
    collection = db[config.COLLECTION_MEMORY_STORE]

    console.print(f"  [yellow]Waiting for index to be ready (up to {timeout_seconds}s)...[/yellow]")

    start = time.time()
    while time.time() - start < timeout_seconds:
        indexes = list(collection.list_search_indexes())
        for idx in indexes:
            if idx.get("name") == config.VECTOR_INDEX_NAME:
                status = idx.get("status")
                if status == "READY":
                    console.print(f"  [green]Index is READY![/green]")
                    return True
                console.print(f"  [dim]Index status: {status}[/dim]")
        time.sleep(3)

    console.print(f"  [red]Timeout waiting for index. Check Atlas UI.[/red]")
    return False


def main(recreate_index: bool = False) -> None:
    """Run the Atlas setup.

    Args:
        recreate_index: If True, delete and recreate the vector search index.
    """
    config.validate_required_env()

    console.print("\n[bold]Event Venue Operator Atlas Setup[/bold]\n")

    console.print("[bold]1. Creating collections...[/bold]")
    create_collections()

    if recreate_index:
        console.print("\n[bold]2. Recreating vector search index...[/bold]")
        deleted = delete_vector_search_index()
        if deleted:
            # Wait a moment for deletion to propagate
            console.print("  [dim]Waiting for deletion to propagate...[/dim]")
            time.sleep(5)
    else:
        console.print("\n[bold]2. Creating vector search index...[/bold]")

    create_vector_search_index()

    console.print("\n[bold]3. Waiting for index to build...[/bold]")
    ready = wait_for_index_ready(timeout_seconds=60)

    if ready:
        console.print("\n[bold green]Setup complete![/bold green] You can now run seed_data.py\n")
    else:
        console.print(
            "\n[bold yellow]Setup initiated but index not yet ready.[/bold yellow]"
            "\nCheck Atlas UI and wait for index status to be READY before seeding.\n"
        )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Set up MongoDB Atlas for Event Venue Operator")
    parser.add_argument(
        "--recreate-index",
        action="store_true",
        help="Delete and recreate the vector search index",
    )
    args = parser.parse_args()
    main(recreate_index=args.recreate_index)
