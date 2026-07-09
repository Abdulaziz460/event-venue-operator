#!/usr/bin/env python3
"""Load event-venue seed data into the guest and fleet namespaces.

Run this after setup_atlas.py:

    uv run python scripts/seed_data.py

Seeds 9 entries for fam_001 (the demo personas) with canonical keys:
- 4 from Visit 1 (v1_court, v1_navigation, v1_gap, v1_churn)
- 3 from Visit 2 (v2_weather, v2_dinner, v2_sat)
- 2 stable preferences (pref_match_focus, pref_premier)

Seeds 6 fleet patterns for event_001 with canonical keys:
- fleet_redirect, fleet_storm_revenue, fleet_churn
- fleet_covered_paths, fleet_first_timer_anchor, fleet_weather_advance

Also seeds operational data:
- Guest profile (Mikiko and Nina demo personas)
- Visit history
- Venues and event metrics
"""

from __future__ import annotations

import sys

from rich.console import Console
from rich.table import Table

# Add src to path for imports
sys.path.insert(0, "src")

from event_venue_operator import config
from event_venue_operator.db import get_collection, get_store, init_venue_status
from event_venue_operator.seed import (
    FLEET_MEMORIES,
    GUEST_MEMORIES,
    GUEST_PROFILE,
    INITIAL_EVENT_METRICS,
    VENUES,
    VISITS,
    get_fleet_namespace,
    get_guest_namespace,
)

console = Console()


def _delete_seeded_keys(namespace: tuple[str, str], keys: list[str]) -> None:
    """Remove prior demo rows that would collide with the store's namespace/key index."""
    if not keys:
        return

    namespace_filters: list[dict[str, object]] = [{"namespace": list(namespace)}]

    get_collection(config.COLLECTION_MEMORY_STORE).delete_many(
        {
            "key": {"$in": keys},
            "$or": namespace_filters,
        }
    )


def _add_namespace_str(namespace: tuple[str, str], namespace_str: str) -> None:
    """Add namespace_str field to memory_store documents for direct vector search.

    MongoDBStore doesn't add this field, but the API's direct Atlas Vector Search
    needs it for filtering. This runs an update after store.put() operations.
    """
    coll = get_collection(config.COLLECTION_MEMORY_STORE)
    result = coll.update_many(
        {"namespace": list(namespace)},
        {"$set": {"namespace_str": namespace_str}},
    )
    if result.modified_count > 0:
        console.print(f"  [dim]Added namespace_str to {result.modified_count} documents[/dim]")


def seed_guest_memories() -> None:
    """Seed the guest namespace with prior-visit memories using canonical keys."""
    namespace = get_guest_namespace()
    namespace_str = "_".join(namespace)  # e.g., "guests_fam_001"

    console.print(f"\n[bold]Seeding guest namespace:[/bold] {namespace}\n")
    _delete_seeded_keys(namespace, [memory["key"] for memory in GUEST_MEMORIES])

    # Create a table to show what we're seeding
    table = Table(title="Guest Memories")
    table.add_column("Key", style="cyan")
    table.add_column("Visit", style="magenta")
    table.add_column("Category", style="yellow")
    table.add_column("Text", style="white", max_width=40)

    for memory in GUEST_MEMORIES:
        val = memory["value"]
        table.add_row(
            memory["key"],
            val["visit_id"],
            val["category"],
            val["text"][:40] + "..." if len(val["text"]) > 40 else val["text"],
        )

    console.print(table)
    console.print()

    # Write entries to the store using canonical keys
    with get_store() as store:
        for memory in GUEST_MEMORIES:
            store.put(
                namespace=namespace,
                key=memory["key"],
                value=memory["value"],
            )
            console.print(f"  [green]Stored:[/green] {memory['key']}")

    # Add namespace_str field for direct API vector search
    _add_namespace_str(namespace, namespace_str)

    console.print(f"\n[bold green]Seeded {len(GUEST_MEMORIES)} guest memories.[/bold green]\n")


def seed_fleet_patterns() -> None:
    """Seed the fleet namespace with operator-level patterns using canonical keys."""
    namespace = get_fleet_namespace()
    namespace_str = "_".join(namespace)  # e.g., "fleet_event_001"

    console.print(f"\n[bold]Seeding fleet namespace:[/bold] {namespace}\n")
    _delete_seeded_keys(namespace, [memory["key"] for memory in FLEET_MEMORIES])

    # Create a table to show what we're seeding
    table = Table(title="Fleet Patterns")
    table.add_column("Key", style="cyan")
    table.add_column("Category", style="magenta")
    table.add_column("Severity", style="yellow")
    table.add_column("Text", style="white", max_width=40)

    for memory in FLEET_MEMORIES:
        val = memory["value"]
        table.add_row(
            memory["key"],
            val["category"],
            val.get("severity", "medium"),
            val["text"][:40] + "..." if len(val["text"]) > 40 else val["text"],
        )

    console.print(table)
    console.print()

    # Write entries to the store using canonical keys
    with get_store() as store:
        for memory in FLEET_MEMORIES:
            store.put(
                namespace=namespace,
                key=memory["key"],
                value=memory["value"],
            )
            console.print(f"  [green]Stored:[/green] {memory['key']}")

    # Add namespace_str field for direct API vector search
    _add_namespace_str(namespace, namespace_str)

    console.print(f"\n[bold green]Seeded {len(FLEET_MEMORIES)} fleet patterns.[/bold green]\n")


def verify_guest_memories() -> None:
    """Verify the seeded guest data by searching the store."""
    namespace = get_guest_namespace()

    console.print("[bold]Verifying guest memories...[/bold]")

    with get_store() as store:
        # Search for entries about court delays
        results = store.search(
            namespace,
            query="court delay suspended match",
            limit=3,
        )

        console.print(f"\n  Search for 'court delay suspended match' returned {len(results)} results:")
        for item in results:
            console.print(f"    - [{item.key}] {item.value.get('text', '')[:50]}...")

        # Search for weather-related entries
        results = store.search(
            namespace,
            query="rain weather covered seating hospitality",
            limit=3,
        )

        console.print(f"\n  Search for 'rain weather covered seating hospitality' returned {len(results)} results:")
        for item in results:
            console.print(f"    - [{item.key}] {item.value.get('text', '')[:50]}...")

    console.print("\n[bold green]Guest memory verification complete![/bold green]\n")


def verify_fleet_patterns() -> None:
    """Verify the seeded fleet data by searching the store."""
    namespace = get_fleet_namespace()

    console.print("[bold]Verifying fleet patterns...[/bold]")

    with get_store() as store:
        # Search for venue redirect patterns
        results = store.search(
            namespace,
            query="outdoor court redirect covered practice",
            limit=3,
        )

        console.print(f"\n  Search for 'outdoor court redirect covered practice' returned {len(results)} results:")
        for item in results:
            console.print(f"    - [{item.key}] {item.value.get('text', '')[:50]}...")

        # Search for weather patterns
        results = store.search(
            namespace,
            query="rain weather hospitality revenue",
            limit=3,
        )

        console.print(f"\n  Search for 'rain weather hospitality revenue' returned {len(results)} results:")
        for item in results:
            console.print(f"    - [{item.key}] {item.value.get('text', '')[:50]}...")

    console.print("\n[bold green]Fleet pattern verification complete![/bold green]\n")


def seed_venue_status() -> None:
    """Initialize status for courts and venue locations."""
    console.print("\n[bold]Initializing venue status...[/bold]")
    init_venue_status()
    console.print("[bold green]Venue status initialized![/bold green]\n")


def seed_operational_data() -> None:
    """Seed operational collections: guests, visits, venues, event_metrics."""
    console.print("\n[bold]Seeding operational data...[/bold]\n")

    # Seed guest profile
    guests_coll = get_collection(config.COLLECTION_GUESTS)
    guests_coll.update_one(
        {"guest_id": GUEST_PROFILE["guest_id"]},
        {"$set": GUEST_PROFILE},
        upsert=True,
    )
    console.print(f"  [green]Guest profile:[/green] {GUEST_PROFILE['family_name']} ({GUEST_PROFILE['guest_id']})")

    # Seed visits
    visits_coll = get_collection(config.COLLECTION_VISITS)
    for visit in VISITS:
        visits_coll.update_one(
            {"visit_id": visit["visit_id"]},
            {"$set": visit},
            upsert=True,
        )
        console.print(f"  [green]Visit:[/green] {visit['visit_id']} - {visit['state']}")

    # Seed venues
    venues_coll = get_collection(config.COLLECTION_VENUES)
    for venue in VENUES:
        venues_coll.update_one(
            {"venue_id": venue["venue_id"]},
            {"$set": venue},
            upsert=True,
        )
        console.print(f"  [green]Venue:[/green] {venue['name']}")

    # Seed event metrics
    metrics_coll = get_collection(config.COLLECTION_EVENT_METRICS)
    metrics_coll.update_one(
        {"event_id": INITIAL_EVENT_METRICS["event_id"], "date": INITIAL_EVENT_METRICS["date"]},
        {"$set": INITIAL_EVENT_METRICS},
        upsert=True,
    )
    console.print(f"  [green]Event metrics:[/green] {INITIAL_EVENT_METRICS['event_id']} for {INITIAL_EVENT_METRICS['date']}")

    console.print("\n[bold green]Operational data seeded![/bold green]\n")


def main() -> None:
    """Run the seed data script."""
    config.validate_required_env()

    console.print("\n[bold]Event Venue Operator Seed Data[/bold]")

    # Seed semantic memory with canonical keys
    seed_guest_memories()
    verify_guest_memories()

    seed_fleet_patterns()
    verify_fleet_patterns()

    # Seed operational data
    seed_operational_data()
    seed_venue_status()


if __name__ == "__main__":
    main()
