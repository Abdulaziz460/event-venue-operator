"""LangGraph StateGraph assembly for the Event Venue Operator agent.

The graph follows the flow: perceive → plan → hitl_gate → act → reflect

The hitl_gate node is a pass-through for MVP (auto-approves all actions).
The reflect node writes inferred signals to the guest namespace.

The graph is compiled with both MongoDBSaver (checkpointer) and MongoDBStore (memory)
passed in — this is the architectural one-liner for Atlas as the converged backend.
"""

from __future__ import annotations

from typing import Any, Iterator

from langgraph.graph import END, START, StateGraph

from event_venue_operator import observability
from event_venue_operator.db import get_checkpointer, get_store_for_graph
from event_venue_operator.nodes import act, hitl_gate, perceive, plan, reflect
from event_venue_operator.state import OperatorState


def build_graph() -> StateGraph:
    """Build the Event Venue Operator agent graph.

    Returns an uncompiled StateGraph. Call compile() with checkpointer and store
    to get a runnable graph.
    """
    graph = StateGraph(OperatorState)

    # Add nodes
    graph.add_node("perceive", perceive)
    graph.add_node("plan", plan)
    graph.add_node("hitl_gate", hitl_gate)
    graph.add_node("act", act)
    graph.add_node("reflect", reflect)

    # Add edges: perceive → plan → hitl_gate → act → reflect → END
    graph.add_edge(START, "perceive")
    graph.add_edge("perceive", "plan")
    graph.add_edge("plan", "hitl_gate")
    graph.add_edge("hitl_gate", "act")
    graph.add_edge("act", "reflect")
    graph.add_edge("reflect", END)

    return graph


def get_compiled_graph():
    """Return a compiled graph with checkpointer and store.

    This is the main entry point for running the agent.
    """
    graph = build_graph()

    # Compile with MongoDB integrations
    # - checkpointer: MongoDBSaver for session state
    # - store: MongoDBStore for semantic memory
    compiled = graph.compile(
        checkpointer=get_checkpointer(),
        store=get_store_for_graph(),
    )

    return compiled


def _summarize_agent_result(result: dict[str, Any]) -> dict[str, Any]:
    """Return a compact, safe Langfuse summary of a graph result."""
    perception = result.get("perception", {}) or {}
    proposed_action = result.get("proposed_action") or {}
    action_result = result.get("action_result") or {}
    action_names = []

    if proposed_action.get("tool_name"):
        action_names.append(proposed_action["tool_name"])
    for extra in proposed_action.get("additional_actions", []) or []:
        if extra.get("tool_name"):
            action_names.append(extra["tool_name"])

    prior_visits = perception.get("prior_visits", {}) or {}

    return {
        "nodes": ["perceive", "plan", "hitl_gate", "act", "reflect"],
        "hitl_decision": result.get("hitl_decision"),
        "proposed_tools": action_names,
        "action_success": action_result.get("success"),
        "action_error": action_result.get("error"),
        "prior_visit_count": len(prior_visits),
        "preference_count": len(perception.get("preferences", []) or []),
        "fleet_pattern_count": len(perception.get("fleet_patterns", []) or []),
        "callback_count": len(result.get("callbacks", []) or []),
        "booking_confirmation_count": len(result.get("booking_confirmations", []) or []),
        "new_signal_count": len(result.get("new_signals", []) or []),
    }


def run_agent(
    guest_id: str = "fam_001",
    visit_id: str = "visit_3",
    thread_id: str | None = None,
) -> dict:
    """Run the Event Venue Operator agent for a guest visit.

    Args:
        guest_id: The guest/family identifier
        visit_id: The visit identifier (also used as thread_id if not specified)
        thread_id: Optional override for the checkpoint thread ID

    Returns:
        The final state after the agent completes
    """
    if thread_id is None:
        thread_id = visit_id

    graph = get_compiled_graph()

    # Initial state
    initial_state: OperatorState = {
        "guest_id": guest_id,
        "visit_id": visit_id,
        "messages": [],
        "perception": {},
        "proposed_action": None,
        "hitl_decision": None,
        "action_result": None,
        "new_signals": [],
    }

    # Run the graph
    config = {"configurable": {"thread_id": thread_id}}
    with observability.trace(
        "langgraph.run_agent",
        input={
            "guest_id": guest_id,
            "visit_id": visit_id,
            "thread_id": thread_id,
        },
        metadata={
            "kind": "langgraph_run",
            "graph": "event_venue_operator",
            "nodes": ["perceive", "plan", "hitl_gate", "act", "reflect"],
        },
    ):
        try:
            result = graph.invoke(initial_state, config)
            observability.update(output=_summarize_agent_result(result))
        except Exception as exc:
            observability.update(
                output={"error": str(exc)},
                metadata={"status": "error", "error_type": exc.__class__.__name__},
            )
            raise
        finally:
            observability.flush()

    return result


def stream_agent(
    guest_id: str = "fam_001",
    visit_id: str = "visit_3",
    thread_id: str | None = None,
) -> Iterator[dict[str, Any]]:
    """Stream the Event Venue Operator agent execution.

    Yields events after each node completes, plus custom streaming events
    emitted by nodes using get_stream_writer().

    Args:
        guest_id: The guest/family identifier
        visit_id: The visit identifier (also used as thread_id if not specified)
        thread_id: Optional override for the checkpoint thread ID

    Yields:
        Dict events containing either:
        - Node state updates (after each node completes)
        - Custom streaming events (activity messages, progress updates)

    Example:
        for event in stream_agent("fam_001", "visit_3"):
            if event.get("type") == "custom":
                # Handle activity message
                print(event["data"]["message"])
            else:
                # Handle node completion
                print(f"Node completed: {event}")
    """
    if thread_id is None:
        thread_id = visit_id

    graph = get_compiled_graph()

    # Initial state with new streaming fields
    initial_state: OperatorState = {
        "guest_id": guest_id,
        "visit_id": visit_id,
        "messages": [],
        "perception": {},
        "proposed_action": None,
        "hitl_decision": None,
        "action_result": None,
        "new_signals": [],
        "callbacks": [],
        "fleet_patterns_used": [],
        "booking_confirmations": [],
    }

    # Stream the graph execution
    # stream_mode options:
    # - "updates": yields state updates after each node
    # - "custom": yields custom events from get_stream_writer()
    config = {"configurable": {"thread_id": thread_id}}

    for event in graph.stream(
        initial_state,
        config,
        stream_mode=["updates", "custom"],
    ):
        yield event
