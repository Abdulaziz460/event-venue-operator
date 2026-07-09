"""Change stream listener for real-time agent perception.

Watches the venue_status and weather_events collections and triggers
agent replans when conditions change.

Usage:
    # In a separate terminal or as a background task:
    uv run python -m event_venue_operator.stream

    # Or import and use directly:
    from event_venue_operator.stream import watch_venue_status, watch_weather_events
    watch_venue_status(callback=my_callback)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Callable

from event_venue_operator import config
from event_venue_operator.db import get_collection, get_mongo_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def watch_venue_status(
    callback: Callable[[dict], None] | None = None,
    guest_id: str = "fam_001",
    visit_id: str = "visit_3",
) -> None:
    """Watch the venue_status collection for changes.

    When a venue status changes (especially to 'closed'), this triggers
    a callback that can invoke the agent to replan.

    Args:
        callback: Function to call when a venue status changes.
                  Receives the change document. If None, logs the change.
        guest_id: The guest ID for agent invocation
        visit_id: The visit ID for agent invocation
    """
    collection = get_collection(config.COLLECTION_VENUE_STATUS)

    # Watch for updates only (inserts handled by initial seed)
    pipeline = [
        {"$match": {"operationType": {"$in": ["update", "replace"]}}}
    ]

    logger.info(f"Starting change stream on {config.COLLECTION_VENUE_STATUS}...")
    logger.info("Watching for venue status changes. Press Ctrl+C to stop.")

    try:
        with collection.watch(pipeline, full_document="updateLookup") as stream:
            for change in stream:
                full_doc = change.get("fullDocument", {})
                location_id = full_doc.get("location_id", "unknown")
                status = full_doc.get("status", "unknown")
                name = full_doc.get("name", location_id)

                logger.info(f"Venue status change: {name} -> {status}")

                # Check if the venue location went offline
                if status in ("closed", "down"):
                    logger.warning(f"VENUE LOCATION DOWN: {name} is now {status}!")

                    if callback:
                        callback({
                            "event_type": "venue_location_down",
                            "location_id": location_id,
                            "location_name": name,
                            "new_status": status,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "guest_id": guest_id,
                            "visit_id": visit_id,
                            "full_document": full_doc,
                        })
                    else:
                        # Default behavior: just log
                        logger.info(f"No callback provided. Would trigger replan for {guest_id}")

    except KeyboardInterrupt:
        logger.info("Change stream stopped by user.")


def watch_weather_events(
    callback: Callable[[dict], None] | None = None,
    guest_id: str = "fam_001",
    visit_id: str = "visit_3",
) -> None:
    """Watch the weather_events collection for new weather alerts.

    When a new weather event is created, this triggers a callback
    that can invoke the agent to book indoor reservations proactively.

    Args:
        callback: Function to call when a weather event is created.
                  Receives the change document. If None, logs the change.
        guest_id: The guest ID for agent invocation
        visit_id: The visit ID for agent invocation
    """
    collection = get_collection(config.COLLECTION_WEATHER_EVENTS)

    # Watch for inserts (new weather events)
    pipeline = [
        {"$match": {"operationType": "insert"}}
    ]

    logger.info(f"Starting change stream on {config.COLLECTION_WEATHER_EVENTS}...")
    logger.info("Watching for weather events. Press Ctrl+C to stop.")

    try:
        with collection.watch(pipeline, full_document="updateLookup") as stream:
            for change in stream:
                full_doc = change.get("fullDocument", {})
                event_type = full_doc.get("event_type", "unknown")
                severity = full_doc.get("severity", "unknown")

                logger.warning(f"WEATHER ALERT: {event_type} (severity: {severity})")

                if callback:
                    callback({
                        "event_type": "weather_alert",
                        "weather_type": event_type,
                        "severity": severity,
                        "forecast_for": full_doc.get("forecast_for"),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "guest_id": guest_id,
                        "visit_id": visit_id,
                        "full_document": full_doc,
                    })
                else:
                    logger.info(f"No callback provided. Would trigger replan for {guest_id}")

    except KeyboardInterrupt:
        logger.info("Weather change stream stopped by user.")


def default_replan_callback(change: dict) -> None:
    """Default callback that triggers an agent replan.

    This invokes the full agent graph when a venue location goes down or weather alert fires.
    """
    from event_venue_operator.graph import run_agent

    guest_id = change.get("guest_id", "fam_001")
    visit_id = change.get("visit_id", "visit_3")
    event_type = change.get("event_type", "unknown")

    if event_type == "venue_location_down":
        location_name = change.get("location_name", "Unknown location")
        logger.info(f"Triggering agent replan for {guest_id} due to {location_name} going down...")
    elif event_type == "weather_alert":
        weather_type = change.get("weather_type", "unknown")
        logger.info(f"Triggering agent replan for {guest_id} due to {weather_type} alert...")
    else:
        logger.info(f"Triggering agent replan for {guest_id}...")

    try:
        result = run_agent(guest_id=guest_id, visit_id=visit_id)
        logger.info(f"Replan complete. Action result: {result.get('action_result', {})}")
    except Exception as e:
        logger.error(f"Replan failed: {e}")


def main() -> None:
    """Run the change stream listener with default settings."""
    config.validate_required_env()

    logger.info("Event Venue Operator Change Stream Listener")
    logger.info("=========================================")

    watch_venue_status(callback=default_replan_callback)


if __name__ == "__main__":
    main()
