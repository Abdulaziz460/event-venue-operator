#!/usr/bin/env python3
"""Dev/debug entry point for invoking the Event Venue Operator agent graph.

Run with:
    uv run python scripts/run_poc.py

This script:
1. Validates environment
2. Runs the agent graph for the tennis rain-delay demo personas
3. Displays the results using rich

Use this for testing the agent without the static FastAPI demo UI.
"""

from __future__ import annotations

import json
import sys

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Add src to path for imports
sys.path.insert(0, "src")

from event_venue_operator import config
from event_venue_operator.db import get_visit
from event_venue_operator.graph import run_agent

console = Console()


def display_perception(perception: dict) -> None:
    """Display the perception data."""
    console.print("\n[bold cyan]Perception[/bold cyan]")

    # Prior visits
    for visit_key in ["visit_1", "visit_2"]:
        visit_data = perception.get("prior_visits", {}).get(visit_key, {})
        if visit_data:
            console.print(f"\n[bold]{visit_key.upper()}:[/bold] {visit_data.get('summary', '')}")
            memories = visit_data.get("memories", [])
            for mem in memories[:3]:  # Show top 3
                console.print(f"  - [{mem.get('category')}] {mem.get('text', '')[:60]}...")

    # Preferences
    prefs = perception.get("preferences", [])
    if prefs:
        console.print("\n[bold]Preferences:[/bold]")
        for pref in prefs:
            console.print(f"  - {pref.get('text', '')}")


def display_itinerary(visit_id: str) -> None:
    """Display the generated itinerary from the visits collection."""
    visit = get_visit(visit_id)
    if not visit:
        console.print("[yellow]No visit document found[/yellow]")
        return

    itinerary = visit.get("planned_actions", [])
    if not itinerary:
        console.print("[yellow]No itinerary in visit document[/yellow]")
        return

    console.print("\n[bold green]Generated Itinerary[/bold green]")

    table = Table(title="Rain-Delay Venue Plan")
    table.add_column("Time", style="cyan", width=10)
    table.add_column("Location / Action", style="magenta", width=20)
    table.add_column("Priority", style="yellow", width=10)
    table.add_column("Annotation", style="white", width=50)

    for stop in itinerary:
        table.add_row(
            stop.get("time", ""),
            stop.get("location", ""),
            stop.get("priority", "normal"),
            stop.get("annotation", "")[:50] + "..." if len(stop.get("annotation", "")) > 50 else stop.get("annotation", ""),
        )

    console.print(table)

    # Show reasoning
    reasoning = visit.get("action_plan_reasoning", "")
    if reasoning:
        console.print(Panel(reasoning, title="Planning Reasoning", border_style="dim"))


def main() -> None:
    """Run the POC demo."""
    config.validate_required_env()

    console.print("\n[bold]Event Venue Operator POC Demo[/bold]")
    console.print("Running agent for Mikiko/Nina tennis rain-delay scenario, visit_3\n")

    console.print("[dim]Starting agent...[/dim]")

    try:
        result = run_agent(
            guest_id=config.DEMO_GUEST_ID,
            visit_id="visit_3",
        )

        console.print("[green]Agent completed successfully![/green]\n")

        # Display perception
        if result.get("perception"):
            display_perception(result["perception"])

        # Display proposed action
        if result.get("proposed_action"):
            console.print("\n[bold yellow]Proposed Action[/bold yellow]")
            action = result["proposed_action"]
            console.print(f"Tool: {action.get('tool_name')}")
            console.print(f"Args: {json.dumps(action.get('tool_args', {}), indent=2)[:600]}...")
            if action.get("reasoning"):
                console.print(f"Reasoning: {action.get('reasoning')[:200]}...")

        # Display action result
        if result.get("action_result"):
            console.print("\n[bold]Action Result[/bold]")
            console.print(json.dumps(result["action_result"], indent=2))

        # Display the saved itinerary
        display_itinerary("visit_3")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
