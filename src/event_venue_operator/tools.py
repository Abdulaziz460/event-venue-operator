"""Agent tools for the Event Venue Operator agent.

These tools are used by the `act` node to execute actions. Each tool writes to
the operational collections (visits, agent_actions) and returns a result.

For the POC, we implement:
- update_itinerary: Update the planned venue itinerary/actions

Tools for later milestones:
- book_reservation: Book a dining/experience reservation
- send_notification: Send a notification to the guest
- request_assistance: Request staff assistance for accessibility needs
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from event_venue_operator import config
from event_venue_operator.db import get_collection, log_agent_action


class ItineraryStop(BaseModel):
    """A single stop or action in the itinerary."""

    time: str = Field(description="Scheduled time for this stop (e.g., '9:30 AM')")
    location: str = Field(description="Name of the venue location, route, or activity")
    annotation: str = Field(
        description="Why this stop was chosen, especially referencing prior-visit context"
    )
    priority: str = Field(
        default="normal",
        description="Priority level: 'high' for must-do items, 'normal' for standard, 'backup' for contingencies",
    )


class UpdateItineraryInput(BaseModel):
    """Input schema for update_itinerary tool."""

    visit_id: str = Field(description="The visit ID to update")
    stops: list[ItineraryStop] = Field(
        description="Ordered list of venue stops or actions for the day"
    )
    reasoning: str = Field(
        description="Explanation of the planning approach and how prior-visit context informed the plan"
    )


class UpdateItineraryOutput(BaseModel):
    """Output schema for update_itinerary tool."""

    success: bool
    message: str
    stop_count: int


class BookReservationInput(BaseModel):
    """Input schema for book_reservation tool."""

    visit_id: str = Field(description="The visit ID to book for")
    venue_type: str = Field(
        description="Type of venue: 'indoor_dining', 'hospitality', 'covered_seating', 'experience'"
    )
    venue_name: str = Field(description="Name of the hospitality venue, covered seating area, or restaurant")
    time: str = Field(description="Reservation time (e.g., '12:30 PM')")
    party_size: int = Field(default=2, description="Number of guests in the party")
    special_requests: str = Field(
        default="",
        description="Special requests (covered seating, hospitality preferences, accessibility needs, etc.)"
    )
    reason: str = Field(
        description="Why this reservation is being made (weather contingency, hospitality protection, etc.)"
    )
    prior_visit_callback: str = Field(
        default="",
        description="Reference to prior-visit incident that motivated this booking"
    )


class BookReservationOutput(BaseModel):
    """Output schema for book_reservation tool."""

    success: bool
    confirmation_number: str
    venue_name: str
    time: str
    message: str
    callback: dict = Field(
        default_factory=dict,
        description="Callback card data showing prior visit → today comparison"
    )


def update_itinerary(input_data: UpdateItineraryInput) -> UpdateItineraryOutput:
    """Update the planned itinerary for a visit.

    Writes the new itinerary to the visits collection and logs the action.
    """
    visits_collection = get_collection(config.COLLECTION_VISITS)

    # Build the itinerary document
    itinerary = [stop.model_dump() for stop in input_data.stops]

    # Update the visit document
    updated_at = datetime.now(timezone.utc).isoformat()
    result = visits_collection.update_one(
        {"visit_id": input_data.visit_id},
        {
            "$set": {
                "planned_actions": itinerary,
                "action_plan_reasoning": input_data.reasoning,
                "action_plan_updated_at": updated_at,
                "itinerary_updated_at": updated_at,
            }
        },
        upsert=True,
    )

    # Log the action
    log_agent_action({
        "visit_id": input_data.visit_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action_type": "update_itinerary",
        "reasoning": input_data.reasoning,
        "input_state": {"stop_count": len(input_data.stops)},
        "result": {"success": True},
    })

    return UpdateItineraryOutput(
        success=True,
        message=f"Itinerary updated with {len(input_data.stops)} stops",
        stop_count=len(input_data.stops),
    )


def book_reservation(input_data: BookReservationInput) -> BookReservationOutput:
    """Book an indoor dining or hospitality reservation.

    Used proactively when weather is forecasted or when a premier guest needs
    a pre-planned covered option. Returns a confirmation that can be
    displayed to the guest with a callback to the prior-visit incident that
    motivated the booking.
    """
    visits_collection = get_collection(config.COLLECTION_VISITS)

    # Generate confirmation number
    timestamp = datetime.now(timezone.utc)
    conf_num = f"RES-{timestamp.strftime('%H%M%S')}-{input_data.venue_type[:3].upper()}"

    # Build the reservation document
    reservation = {
        "confirmation_number": conf_num,
        "venue_type": input_data.venue_type,
        "venue_name": input_data.venue_name,
        "time": input_data.time,
        "party_size": input_data.party_size,
        "special_requests": input_data.special_requests,
        "reason": input_data.reason,
        "booked_at": timestamp.isoformat(),
        "status": "confirmed",
    }

    # Add reservation to the visit document
    visits_collection.update_one(
        {"visit_id": input_data.visit_id},
        {
            "$push": {"reservations": reservation},
            "$set": {"reservations_updated_at": timestamp.isoformat()},
        },
        upsert=True,
    )

    # Build callback card data
    callback = {}
    if input_data.prior_visit_callback:
        callback = {
            "prior_visit": "visit_2" if "thunderstorm" in input_data.prior_visit_callback.lower() or "weather" in input_data.prior_visit_callback.lower() else "visit_1",
            "prior_text": input_data.prior_visit_callback,
            "current_text": f"Indoor reservation booked at {input_data.venue_name} for {input_data.time}",
        }

    # Log the action
    log_agent_action({
        "visit_id": input_data.visit_id,
        "timestamp": timestamp.isoformat(),
        "action_type": "book_reservation",
        "reasoning": input_data.reason,
        "input_state": {
            "venue_type": input_data.venue_type,
            "venue_name": input_data.venue_name,
            "time": input_data.time,
            "party_size": input_data.party_size,
        },
        "result": {
            "success": True,
            "confirmation_number": conf_num,
        },
    })

    return BookReservationOutput(
        success=True,
        confirmation_number=conf_num,
        venue_name=input_data.venue_name,
        time=input_data.time,
        message=f"Reservation confirmed at {input_data.venue_name} for {input_data.time}",
        callback=callback,
    )


# Tool registry for the agent
TOOLS: dict[str, Any] = {
    "update_itinerary": {
        "function": update_itinerary,
        "input_schema": UpdateItineraryInput,
        "output_schema": UpdateItineraryOutput,
        "description": (
            "Update the planned venue itinerary/actions for the visit. "
            "Include stops with times, locations, and annotations explaining "
            "why each stop was chosen based on prior-visit context."
        ),
    },
    "book_reservation": {
        "function": book_reservation,
        "input_schema": BookReservationInput,
        "output_schema": BookReservationOutput,
        "description": (
            "Book an indoor dining, covered seating, or hospitality reservation proactively. "
            "Use this when weather is forecasted, when a premier guest needs "
            "pre-planned covered options, or when prior-visit incidents (like Visit 2's "
            "rain delay with no covered hospitality contingency) motivate a proactive booking. "
            "Include the prior_visit_callback field to reference the specific incident "
            "that motivated this booking."
        ),
    },
}


def get_tool_descriptions() -> list[dict]:
    """Return tool descriptions formatted for Claude."""
    return [
        {
            "name": name,
            "description": tool["description"],
            "input_schema": tool["input_schema"].model_json_schema(),
        }
        for name, tool in TOOLS.items()
    ]


def execute_tool(name: str, arguments: dict) -> dict:
    """Execute a tool by name with the given arguments."""
    if name not in TOOLS:
        return {"error": f"Unknown tool: {name}"}

    tool = TOOLS[name]
    try:
        input_data = tool["input_schema"](**arguments)
        result = tool["function"](input_data)
        return result.model_dump()
    except Exception as e:
        return {"error": str(e)}
