"""LangGraph nodes for the Event Venue Operator agent.

Implements the full perceive → plan → hitl_gate → act → reflect loop:
- perceive: Retrieves prior-visit memories, fleet patterns, and current context
- plan: Claude generates an itinerary based on perception + memory
- hitl_gate: Human-in-the-loop approval (pass-through for MVP, active in V2)
- act: Executes the approved action
- reflect: Write new inferred signals to the store
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.config import get_stream_writer

from event_venue_operator import config
from event_venue_operator.db import get_active_weather_event, get_current_venue_status, get_store
from event_venue_operator.seed import get_fleet_namespace, get_guest_namespace
from event_venue_operator.state import OperatorState
from event_venue_operator.tools import execute_tool, get_tool_descriptions


def _get_llm():
    """Initialize Claude via init_chat_model."""
    return init_chat_model(
        model=config.DEFAULT_MODEL,
        model_provider="anthropic",
        api_key=config.ANTHROPIC_API_KEY,
    )


def perceive(state: OperatorState) -> dict[str, Any]:
    """Perceive node: gather context from memory and operational data.

    Retrieves prior event memories, stable preferences, operator patterns,
    current venue status, and active weather.

    Returns a perception dict that the plan node will use.
    """
    writer = get_stream_writer()

    guest_id = state.get("guest_id", config.DEMO_GUEST_ID)
    visit_id = state.get("visit_id", "visit_3")

    guest_namespace = get_guest_namespace()
    fleet_namespace = get_fleet_namespace()

    # Emit streaming event: starting memory retrieval
    writer({"type": "activity", "node": "perceive", "icon": "magnifying_glass",
            "message": "Searching guest memory..."})

    # Retrieve prior-visit memories using vector search
    prior_memories: list[dict] = []
    fleet_patterns: list[dict] = []

    with get_store() as store:
        # Search for memories related to past incidents and experiences
        # We do multiple searches to cover different aspects
        guest_queries = [
            "court delay suspended match missed start",
            "weather rain storm covered seating hospitality",
            "wayfinding first time visitor route food village",
            "satisfaction complaint disappointment",
            "preference premier covered seating match focused",
        ]

        seen_keys: set[str] = set()
        for query in guest_queries:
            results = store.search(guest_namespace, query=query, limit=5)
            for item in results:
                if item.key not in seen_keys:
                    seen_keys.add(item.key)
                    prior_memories.append({
                        "key": item.key,
                        **item.value,
                    })

        # Emit streaming event: found memories
        writer({"type": "activity", "node": "perceive", "icon": "clipboard",
                "message": f"Found {len(prior_memories)} prior-visit memories"})

        # Emit streaming event: searching fleet patterns
        writer({"type": "activity", "node": "perceive", "icon": "gear",
                "message": "Loading fleet patterns..."})

        # Search for fleet patterns (operator-level knowledge)
        fleet_queries = [
            "outdoor court suspended redirect covered practice",
            "rain weather indoor hospitality reservation",
            "first time visitor route recommendation",
        ]

        seen_fleet_keys: set[str] = set()
        for query in fleet_queries:
            results = store.search(fleet_namespace, query=query, limit=3)
            for item in results:
                if item.key not in seen_fleet_keys:
                    seen_fleet_keys.add(item.key)
                    fleet_patterns.append({
                        "key": item.key,
                        **item.value,
                    })

        # Emit streaming event: fleet patterns loaded
        writer({"type": "activity", "node": "perceive", "icon": "check",
                "message": f"Loaded {len(fleet_patterns)} fleet patterns"})

    # Group memories by visit
    visit_1_memories = [m for m in prior_memories if m.get("visit_id") == "visit_1"]
    visit_2_memories = [m for m in prior_memories if m.get("visit_id") == "visit_2"]
    preferences = [m for m in prior_memories if m.get("visit_id") == "all"]

    # Get current venue status and weather
    venue_status = get_current_venue_status()
    weather_event = get_active_weather_event()

    # Determine weather description
    if weather_event:
        weather_desc = (
            f"ALERT: {weather_event['event_type']} forecast - "
            f"severity: {weather_event['severity']}, "
            f"expected at: {weather_event['forecast_for']}"
        )
    else:
        weather_desc = "clear morning, possible afternoon clouds"

    perception = {
        "guest_id": guest_id,
        "visit_id": visit_id,
        "prior_visits": {
            "visit_1": {
                "summary": "Mikiko's first visit ~12 months ago - suspended court, confusing wayfinding, missed match start",
                "memories": visit_1_memories,
            },
            "visit_2": {
                "summary": "Nina's premier visit ~6 months ago - rain delay, no covered contingency, missed hospitality dinner",
                "memories": visit_2_memories,
            },
        },
        "preferences": preferences,
        "fleet_patterns": fleet_patterns,
        "family_context": {
            "members": [
                {"name": "Mikiko", "role": "first-time visitor", "needs": "clear routing to active courts and first-time-friendly options"},
                {"name": "Nina", "role": "premier guest", "needs": "covered seating, hospitality continuity, protected dining reservation"},
            ],
        },
        "current_conditions": {
            "weather": weather_desc,
            "weather_event": weather_event,
            "venue_summary": "tournament operations",
            "venue_status": venue_status,
        },
    }

    return {"perception": perception}


def _extract_callbacks_from_stops(stops: list[dict]) -> list[dict]:
    """Extract callback cards from itinerary stop annotations.

    Looks for references to prior visits in annotations and creates
    callback cards that show "prior visit problem → today's solution".
    """
    callbacks = []

    # Patterns to identify prior-visit references
    visit_patterns = [
        (r"[Vv]isit\s*1|[Vv]isit\s*one|12\s*months?\s*ago|last\s*year", "visit_1"),
        (r"[Vv]isit\s*2|[Vv]isit\s*two|6\s*months?\s*ago", "visit_2"),
    ]

    # Keywords indicating problems
    problem_keywords = [
        "breakdown", "broke down", "downtime", "waited", "wait",
        "exhausted", "fatigue", "missed", "stuck", "caught",
        "thunderstorm", "storm", "rain", "shelter", "stranded"
    ]

    for stop in stops:
        annotation = stop.get("annotation", "").lower()

        # Check each visit pattern
        for pattern, visit_id in visit_patterns:
            if re.search(pattern, annotation, re.IGNORECASE):
                # Found a visit reference, check for problem keywords
                for keyword in problem_keywords:
                    if keyword in annotation:
                        callbacks.append({
                            "prior_visit": visit_id,
                            "prior_text": _summarize_prior_problem(annotation, visit_id),
                            "current_text": f"Today: {stop.get('location', 'Action')} scheduled proactively",
                            "stop_time": stop.get("time", ""),
                            "location": stop.get("location", ""),
                        })
                        break
                break

    # Deduplicate by visit_id (keep first callback per visit)
    seen_visits = set()
    unique_callbacks = []
    for cb in callbacks:
        if cb["prior_visit"] not in seen_visits:
            seen_visits.add(cb["prior_visit"])
            unique_callbacks.append(cb)

    return unique_callbacks


def _summarize_prior_problem(annotation: str, visit_id: str) -> str:
    """Create a brief summary of the prior-visit problem referenced."""
    if visit_id == "visit_1":
        if "breakdown" in annotation or "broke down" in annotation or "downtime" in annotation:
            return "Court suspension caused unmanaged waiting"
        if "wayfinding" in annotation or "missed" in annotation:
            return "Mikiko missed match time due to confusing routing"
        return "Visit 1: First-time visitor flow broke down"
    elif visit_id == "visit_2":
        if "thunderstorm" in annotation or "storm" in annotation or "rain" in annotation:
            return "Caught in thunderstorm with no indoor plan"
        if "missed" in annotation and "reservation" in annotation:
            return "Hospitality reservation missed due to weather"
        return "Visit 2: Weather caught premier guest unprepared"
    return f"{visit_id}: Prior incident"


def _fallback_venue_plan(visit_id: str) -> dict[str, Any]:
    """Return a valid tennis rain-delay plan if the LLM emits malformed tool args."""
    return {
        "visit_id": visit_id,
        "stops": [
            {
                "time": "2:15 PM",
                "location": "Covered Practice Court",
                "priority": "high",
                "annotation": (
                    "Mikiko gets one clear first-timer route after Visit 1's court "
                    "suspension and missed match start."
                ),
            },
            {
                "time": "2:20 PM",
                "location": "Premier Club Lounge",
                "priority": "high",
                "annotation": (
                    "Nina is moved to covered premier seating before rain repeats "
                    "Visit 2's unmanaged sheltering issue."
                ),
            },
            {
                "time": "2:30 PM",
                "location": "Champions Dining Room",
                "priority": "backup",
                "annotation": (
                    "Protect the hospitality dinner window that was missed during "
                    "Nina's prior rain-disrupted visit."
                ),
            },
        ],
        "reasoning": (
            "Fallback venue plan generated because the LLM returned incomplete "
            "tool arguments. It preserves the retrieved Mikiko/Nina rain-delay "
            "context and writes a valid plan to Atlas."
        ),
    }


def _normalize_update_itinerary_args(args: dict[str, Any], visit_id: str) -> dict[str, Any]:
    """Normalize or replace malformed update_itinerary arguments."""
    if args.get("stops"):
        normalized = dict(args)
        normalized.setdefault("visit_id", visit_id)
        normalized.setdefault(
            "reasoning",
            "Generated from retrieved tennis-event memories and current venue conditions.",
        )
        return normalized

    for alternate_key in ("itinerary", "plan", "actions", "venue_plan", "steps"):
        maybe_stops = args.get(alternate_key)
        if isinstance(maybe_stops, list) and maybe_stops:
            normalized_stops = []
            for idx, item in enumerate(maybe_stops, start=1):
                if isinstance(item, dict):
                    normalized_stops.append({
                        "time": str(item.get("time", f"Step {idx}")),
                        "location": str(
                            item.get("location")
                            or item.get("attraction")
                            or item.get("action")
                            or item.get("venue")
                            or "Venue action"
                        ),
                        "annotation": str(
                            item.get("annotation")
                            or item.get("reason")
                            or item.get("description")
                            or "Chosen from retrieved tennis-event context."
                        ),
                        "priority": str(item.get("priority", "normal")),
                    })
                else:
                    normalized_stops.append({
                        "time": f"Step {idx}",
                        "location": "Venue action",
                        "annotation": str(item),
                        "priority": "normal",
                    })
            return {
                "visit_id": args.get("visit_id", visit_id),
                "stops": normalized_stops,
                "reasoning": args.get(
                    "reasoning",
                    "Normalized LLM plan from alternate tool-argument shape.",
                ),
            }

    return _fallback_venue_plan(visit_id)


def plan(state: OperatorState) -> dict[str, Any]:
    """Plan node: Claude generates a venue-operations plan based on perception."""
    writer = get_stream_writer()

    perception = state.get("perception", {})
    visit_id = state.get("visit_id", "visit_3")

    # Emit streaming event: starting planning
    writer({"type": "activity", "node": "plan", "icon": "brain",
            "message": "Planning itinerary with Claude..."})

    # Check if there's an active weather event
    weather_event = perception.get("current_conditions", {}).get("weather_event")
    has_weather_alert = weather_event is not None

    # Build the system prompt
    system_prompt = """You are an AI agent for a premium tennis event venue operator.
Your job is to create proactive, persona-specific actions during a rain-delay scenario.

You have access to prior event memories and preferences for two demo personas:
- Mikiko: first-time visitor, match-focused, needs clear routing and low-friction guidance.
- Nina: premier guest, values covered seating, hospitality continuity, and protected dining.

Use this context to:
1. Acknowledge what went wrong during prior event visits.
2. Plan around those failure modes proactively.
3. Give Mikiko and Nina different actions based on their personas.
4. Build in covered/indoor contingencies before rain disrupts the grounds.

When creating the plan, reference specific prior incidents in annotations to show
that the venue remembers and has learned from past experiences.

Available locations:
- Centre Court (covered show court)
- Court 1 (covered show court)
- Court 2 (outdoor court; vulnerable during rain)
- Covered Practice Court (good first-timer redirect)
- Champions Lounge (premier hospitality)
- Food Village (outdoor concessions; vulnerable during rain)
- Baseline Cafe (covered cafe)
- Champions Dining Room (premier indoor dining)
- Premier Club Lounge (covered premier experience)

TOOLS:
- update_itinerary: Use this to save the planned venue-operations plan
- book_reservation: Use this IMMEDIATELY when there's a weather alert to book an indoor
  hospitality or dining reservation. On Visit 2, Nina was caught in rain with no covered
  plan and missed a hospitality dinner window. Include the prior_visit_callback field.

You must call update_itinerary to save the plan. If there's a weather alert, ALSO call
book_reservation to secure covered hospitality before capacity fills."""

    # Build the user message with context
    fleet_patterns = perception.get('fleet_patterns', [])
    fleet_patterns_text = json.dumps(fleet_patterns, indent=2) if fleet_patterns else "No fleet patterns available"

    venue_status = perception.get('current_conditions', {}).get('venue_status', [])
    venue_status_text = json.dumps(venue_status, indent=2) if venue_status else "All venue locations operational"

    # Build weather alert section if needed
    weather_alert_section = ""
    if has_weather_alert:
        weather_alert_section = f"""
### ⚠️ WEATHER ALERT - ACTION REQUIRED
{json.dumps(weather_event, indent=2)}

CRITICAL: On Visit 2, Nina was caught in rain with NO covered-premier contingency.
She sheltered outdoors, missed her hospitality dinner window, and rated the experience 2/5.

You MUST call book_reservation IMMEDIATELY to secure covered hospitality before capacity fills.
Use prior_visit_callback to reference the Visit 2 thunderstorm incident.
"""

    user_message = f"""Create a rain-delay venue-operations plan for the Premier Tennis Tournament.

## Prior Visit Context

### Visit 1 (~12 months ago)
{json.dumps(perception.get('prior_visits', {}).get('visit_1', {}), indent=2)}

### Visit 2 (~6 months ago)
{json.dumps(perception.get('prior_visits', {}).get('visit_2', {}), indent=2)}

### Persona Preferences
{json.dumps(perception.get('preferences', []), indent=2)}

### Personas
{json.dumps(perception.get('family_context', {}).get('members', []), indent=2)}

### Fleet Patterns (Operator-Level Knowledge)
{fleet_patterns_text}

### Current Conditions
Weather: {perception.get('current_conditions', {}).get('weather', 'unknown')}
Venue Summary: {perception.get('current_conditions', {}).get('venue_summary', 'unknown')}
{weather_alert_section}
### Current Location Status
{venue_status_text}

Create a plan for visit_id: {visit_id}

Remember to:
- Give Mikiko one clear first-timer next step to avoid another missed match start
- Protect Nina's covered seating and hospitality path before the rain hits
- Book an indoor hospitality backup early (learning from Visit 2's missed dinner window)
- Use operator patterns to inform covered routing and redirect strategies
- Reference specific prior incidents in your stop annotations
- Use venue/tournament language consistently
{"- IMMEDIATELY book a covered hospitality reservation due to weather alert!" if has_weather_alert else ""}

Call the update_itinerary tool with your plan{" AND book_reservation for weather contingency" if has_weather_alert else ""}."""

    # Get tool descriptions
    tools = get_tool_descriptions()

    # Call Claude
    llm = _get_llm()
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_message),
    ]

    # Bind tools to the model
    llm_with_tools = llm.bind_tools(tools)
    response = llm_with_tools.invoke(messages)

    # Emit streaming event: plan generated
    writer({"type": "activity", "node": "plan", "icon": "sparkles",
            "message": "Itinerary generated"})

    # Extract all tool calls
    proposed_actions: list[dict] = []
    callbacks: list[dict] = []
    fleet_patterns_used: list[dict] = []

    if response.tool_calls:
        for tool_call in response.tool_calls:
            tool_args = tool_call["args"]
            if tool_call["name"] == "update_itinerary":
                tool_args = _normalize_update_itinerary_args(tool_args, visit_id)

            action = {
                "tool_name": tool_call["name"],
                "tool_args": tool_args,
                "reasoning": response.content if response.content else "Generated based on prior-visit context",
            }
            proposed_actions.append(action)

            # Extract callbacks from itinerary stops
            if tool_call["name"] == "update_itinerary":
                stops = tool_args.get("stops", [])
                itinerary_callbacks = _extract_callbacks_from_stops(stops)
                callbacks.extend(itinerary_callbacks)

            # Extract callback from book_reservation
            elif tool_call["name"] == "book_reservation":
                prior_callback = tool_call["args"].get("prior_visit_callback", "")
                if prior_callback:
                    callbacks.append({
                        "prior_visit": "visit_2",
                        "prior_text": prior_callback,
                        "current_text": f"Indoor reservation booked at {tool_call['args'].get('venue_name', 'venue')}",
                        "location": tool_call["args"].get("venue_name", ""),
                    })
                writer({"type": "activity", "node": "plan", "icon": "calendar",
                        "message": f"Booking indoor reservation at {tool_call['args'].get('venue_name', 'venue')}"})

        if callbacks:
            writer({"type": "activity", "node": "plan", "icon": "link",
                    "message": f"Found {len(callbacks)} prior-visit callback(s)"})

        # Surface fleet patterns that were used
        fleet_patterns_used = perception.get("fleet_patterns", [])

    # For backward compatibility, use first action as proposed_action
    # but store all actions for the act node to execute
    proposed_action = proposed_actions[0] if proposed_actions else None
    if len(proposed_actions) > 1:
        # Store additional actions in proposed_action
        proposed_action["additional_actions"] = proposed_actions[1:]

    return {
        "proposed_action": proposed_action,
        "callbacks": callbacks,
        "fleet_patterns_used": fleet_patterns_used,
        "messages": state.get("messages", []) + [response],
    }


def hitl_gate(state: OperatorState) -> dict[str, Any]:
    """Human-in-the-loop gate node.

    For MVP, this is a pass-through that auto-approves all actions.
    In V2, this will surface high-stakes actions to the operator for approval,
    with conditional edges handling approve/deny/escalate paths.
    """
    proposed_action = state.get("proposed_action")

    if not proposed_action:
        return {"hitl_decision": "approved"}

    # MVP: Auto-approve everything
    # V2: Check action type and risk level, potentially interrupt for human approval
    return {"hitl_decision": "approved"}


def act(state: OperatorState) -> dict[str, Any]:
    """Act node: execute the approved action(s).

    Only executes if hitl_decision is "approved".
    Handles multiple actions (e.g., update_itinerary + book_reservation).
    """
    writer = get_stream_writer()

    hitl_decision = state.get("hitl_decision")
    proposed_action = state.get("proposed_action")

    if hitl_decision != "approved":
        writer({"type": "activity", "node": "act", "icon": "x",
                "message": f"Action blocked: {hitl_decision}"})
        return {
            "action_result": {"error": f"Action not approved: {hitl_decision}"},
        }

    if not proposed_action:
        return {
            "action_result": {"error": "No action proposed"},
        }

    # Collect all actions to execute
    actions_to_execute = [proposed_action]
    if "additional_actions" in proposed_action:
        actions_to_execute.extend(proposed_action["additional_actions"])

    # Execute all actions
    results = []
    booking_confirmations = []

    for action in actions_to_execute:
        tool_name = action.get("tool_name")
        tool_args = action.get("tool_args", {})

        # Emit streaming event: executing action
        writer({"type": "activity", "node": "act", "icon": "rocket",
                "message": f"Executing: {tool_name}..."})

        # Execute the tool
        result = execute_tool(tool_name, tool_args)
        results.append(result)

        # Emit streaming event: action complete
        if result.get("success"):
            writer({"type": "activity", "node": "act", "icon": "check",
                    "message": f"Action complete: {result.get('message', 'Success')}"})

            # Track booking confirmations
            if tool_name == "book_reservation":
                booking_confirmations.append({
                    "confirmation_number": result.get("confirmation_number", ""),
                    "venue_name": result.get("venue_name", ""),
                    "time": result.get("time", ""),
                    "callback": result.get("callback", {}),
                })
                writer({"type": "activity", "node": "act", "icon": "party_popper",
                        "message": f"Reservation confirmed: {result.get('confirmation_number', '')}"})
        else:
            writer({"type": "activity", "node": "act", "icon": "warning",
                    "message": f"Action failed: {result.get('error', 'Unknown error')}"})

    # Combine results - use first result as primary, include all
    primary_result = results[0] if results else {"error": "No results"}
    if len(results) > 1:
        primary_result["additional_results"] = results[1:]

    return {
        "action_result": primary_result,
        "booking_confirmations": booking_confirmations,
    }


def reflect(state: OperatorState) -> dict[str, Any]:
    """Reflect node: observe behavior and write new inferences to the store.

    Analyzes the current visit's events and writes any new learned signals
    to the guest namespace with a visit_3 tag. This is how the agent builds
    memory from today's visit that will inform future visits.

    Examples of inferences:
    - Mikiko followed a first-timer route during a court delay
    - Nina accepted a covered hospitality rebooking
    - Guests moved indoors before rain reached the grounds
    """
    writer = get_stream_writer()

    visit_id = state.get("visit_id", "visit_3")
    action_result = state.get("action_result", {})
    perception = state.get("perception", {})

    new_signals: list[dict] = []

    # For now, we generate a simple inference based on the successful plan
    # In a full implementation, this would analyze actual visit events
    if action_result.get("success"):
        # Record that a proactive plan was generated and accepted
        new_signals.append({
            "text": (
                "Mikiko and Nina received a proactive rain-delay plan addressing prior "
                "event pain points (court delay, wayfinding, covered hospitality, weather contingency)"
            ),
            "category": "behavior_pattern",
            "visit_id": visit_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "severity": "low",
        })

    # Write new signals to the store
    if new_signals:
        writer({"type": "activity", "node": "reflect", "icon": "lightbulb",
                "message": f"Learning {len(new_signals)} new signal(s)..."})

        namespace = get_guest_namespace()
        with get_store() as store:
            for signal in new_signals:
                key = f"{visit_id}_{signal['category']}_{uuid.uuid4().hex[:8]}"
                store.put(namespace, key, signal)

        writer({"type": "activity", "node": "reflect", "icon": "floppy_disk",
                "message": "Memory updated for future visits"})
    else:
        writer({"type": "activity", "node": "reflect", "icon": "memo",
                "message": "No new signals to record"})

    return {"new_signals": new_signals}
