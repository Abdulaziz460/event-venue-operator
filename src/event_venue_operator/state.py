"""LangGraph state schema for the Event Venue Operator agent.

The `OperatorState` TypedDict flows through every node in the graph. Each node
reads from the state and returns a partial dict that LangGraph merges into the
next invocation.
"""

from __future__ import annotations

from typing import Any, Literal, TypedDict

from langchain_core.messages import BaseMessage


class OperatorState(TypedDict, total=False):
    """State carried through the perceive → plan → hitl_gate → act → reflect loop.

    All fields are `total=False` because each node only writes the subset it
    produces. LangGraph merges the partial dicts.

    Attributes
    ----------
    visit_id
        Identifier for today's visit. Also used as the LangGraph `thread_id`
        so MongoDBSaver checkpoints are scoped to this visit.
    guest_id
        Identifier for the family. Used as the suffix of the guest namespace
        `("guests", guest_id)` in MongoDBStore.
    messages
        Conversation history for this graph run. LangGraph-managed.
    perception
        Output of the `perceive` node. Dict containing current itinerary,
        retrieved prior-visit memories, fleet patterns, and live operational
        state (venue status, weather).
    proposed_action
        Output of the `plan` node. Dict describing what the agent wants to do:
        which tool to call with which arguments, plus the reasoning trace.
        None before the plan node runs.
    hitl_decision
        Output of the `hitl_gate` node. In MVP, always `"approved"` (pass-through).
        In V2, can be `"denied"` or `"escalated"` with conditional edges handling
        each path.
    action_result
        Output of the `act` node. Dict recording what the tool did and any
        return value. None before act runs.
    new_signals
        Output of the `reflect` node. List of memory entries to write to the
        guest namespace. Empty list if nothing new was learned.
    callbacks
        Extracted callback cards showing prior visit → today comparison.
        Each dict has: prior_visit, prior_text, current_text.
    fleet_patterns_used
        Fleet patterns that informed the current decision. Surfaced from
        perception for UI display.
    booking_confirmations
        List of booking confirmations made during this run (reservations, etc.)
    """

    visit_id: str
    guest_id: str
    messages: list[BaseMessage]
    perception: dict[str, Any]
    proposed_action: dict[str, Any] | None
    hitl_decision: Literal["approved", "denied", "escalated"] | None
    action_result: dict[str, Any] | None
    new_signals: list[dict[str, Any]]
    # Streaming and demo-related fields
    callbacks: list[dict[str, Any]]
    fleet_patterns_used: list[dict[str, Any]]
    booking_confirmations: list[dict[str, Any]]
