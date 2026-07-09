"""Seed data for the event-venue demo namespaces."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Final

from event_venue_operator import benchmarks, config


GUEST_MEMORIES: Final[list[dict[str, Any]]] = [
    {
        "key": "v1_court",
        "value": {
            "text": "On Mikiko's first tournament visit, Court 2 was suspended after she had already queued outside for 35 minutes; no covered alternate court was suggested.",
            "category": "court_delay",
            "visit_id": "visit_1",
            "severity": "high",
        },
    },
    {
        "key": "v1_navigation",
        "value": {
            "text": "Mikiko spent 25 minutes finding the food village and missed the start of a doubles match; first-time visitors need clear routing when schedules change.",
            "category": "first_timer_navigation",
            "visit_id": "visit_1",
            "severity": "medium",
        },
    },
    {
        "key": "v1_gap",
        "value": {
            "text": "Mikiko wanted to discover smaller courts and practice sessions, but the schedule surfaced only headline matches; exploration intent was not supported.",
            "category": "experience_gap",
            "visit_id": "visit_1",
            "severity": "medium",
        },
    },
    {
        "key": "v1_churn",
        "value": {
            "text": "Mikiko left the grounds before the evening session and rated wayfinding 2 out of 5 after the delayed court and missed match start.",
            "category": "satisfaction_low",
            "visit_id": "visit_1",
            "severity": "high",
        },
    },
    {
        "key": "v2_weather",
        "value": {
            "text": "A rain cell arrived during Nina's prior premier visit with no proactive covered-seat or lounge contingency; she waited under a concourse overhang for 40 minutes.",
            "category": "weather_incident",
            "visit_id": "visit_2",
            "severity": "high",
        },
    },
    {
        "key": "v2_dinner",
        "value": {
            "text": "Nina missed a hospitality dinner window because storm sheltering delayed movement from Centre Court to the dining suite; no proactive rebooking was offered.",
            "category": "missed_reservation",
            "visit_id": "visit_2",
            "severity": "medium",
        },
    },
    {
        "key": "v2_sat",
        "value": {
            "text": "Nina rated the prior premier experience 2 out of 5; she cited lack of weather planning and the missed hospitality window as primary disappointments.",
            "category": "satisfaction_low",
            "visit_id": "visit_2",
            "severity": "medium",
        },
    },
    {
        "key": "pref_match_focus",
        "value": {
            "text": "Mikiko is match-focused and prefers clear guidance to active courts, practice sessions, and first-time-friendly food options rather than generic venue promotions.",
            "category": "preference",
            "visit_id": "all",
            "severity": "low",
        },
    },
    {
        "key": "pref_premier",
        "value": {
            "text": "Nina is a premier guest who values covered seating, hospitality continuity, fast indoor routing, and proactive reservation protection during weather disruptions.",
            "category": "preference",
            "visit_id": "all",
            "severity": "medium",
        },
    },
]


FLEET_MEMORIES: Final[list[dict[str, Any]]] = [
    {
        "key": "fleet_redirect",
        "value": {
            "text": f"When an outdoor show court is suspended, first-time visitors successfully redirect to covered practice courts or indoor activation areas within 20 minutes at a 73% rate across ~{benchmarks.FLEET_REDIRECT_INCIDENTS:,} prior redirects observed.",
            "category": "redirect_pattern",
            "visit_id": "fleet",
            "severity": "medium",
        },
    },
    {
        "key": "fleet_storm_revenue",
        "value": {
            "text": f"Storm forecasts delivered 30 or more minutes in advance shift attendee spend from outdoor concessions to covered hospitality and indoor dining at 3.4x baseline conversion, across ~{benchmarks.FLEET_WEATHER_EVENTS:,} weather events.",
            "category": "revenue_pattern",
            "visit_id": "fleet",
            "severity": "high",
        },
    },
    {
        "key": "fleet_churn",
        "value": {
            "text": "Guests who experience 30 or more minutes of unmanaged rain-delay waiting show 3.2x early-departure risk; proactive covered routing is the strongest intervention.",
            "category": "churn_pattern",
            "visit_id": "fleet",
            "severity": "high",
        },
    },
    {
        "key": "fleet_covered_paths",
        "value": {
            "text": "Guests routed to covered paths before rain onset spend 2.1x longer dwell time in operator-owned hospitality venues versus guests routed after rain begins.",
            "category": "accessibility_pattern",
            "visit_id": "fleet",
            "severity": "medium",
        },
    },
    {
        "key": "fleet_first_timer_anchor",
        "value": {
            "text": "First-time visitors respond best to a single recommended next action during disruptions; too many alternatives increase abandonment and missed match starts.",
            "category": "behavior_pattern",
            "visit_id": "fleet",
            "severity": "medium",
        },
    },
    {
        "key": "fleet_weather_advance",
        "value": {
            "text": "Hospitality reservations protected 30 or more minutes before storm onset show 94% retention versus 58% retention for at-storm rebookings.",
            "category": "revenue_pattern",
            "visit_id": "fleet",
            "severity": "high",
        },
    },
]


ALL_SEED_ENTRIES: Final[list[dict[str, Any]]] = [m["value"] for m in GUEST_MEMORIES]
ALL_FLEET_PATTERNS: Final[list[dict[str, Any]]] = [m["value"] for m in FLEET_MEMORIES]


GUEST_PROFILE: Final[dict[str, Any]] = {
    "guest_id": config.DEMO_GUEST_ID,
    "family_name": "Premier Tennis Demo Guests",
    "party_size": 2,
    "home_location": "London, UK",
    "members": [
        {
            "member_id": "mikiko",
            "name": "Mikiko",
            "role": "first_timer",
            "flags": ["first_time_visitor", "match_focused", "wayfinding_help"],
        },
        {
            "member_id": "nina",
            "name": "Nina",
            "role": "premier_guest",
            "flags": ["premier_access", "covered_seating", "hospitality_priority"],
        },
    ],
}


def _iso(dt: datetime) -> str:
    return dt.replace(microsecond=0, tzinfo=timezone.utc).isoformat()


def _build_visits() -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc)
    return [
        {
            "visit_id": "visit_1",
            "guest_id": config.DEMO_GUEST_ID,
            "event_id": config.DEMO_EVENT_ID,
            "visit_date": _iso(now - timedelta(days=365)),
            "satisfaction": 2.0,
            "venue_spend": benchmarks.PERSONA_V1_SPEND,
            "summary": "Mikiko's first visit had a suspended court, confusing wayfinding, and a missed match start.",
            "state": "closed_bad",
        },
        {
            "visit_id": "visit_2",
            "guest_id": config.DEMO_GUEST_ID,
            "event_id": config.DEMO_EVENT_ID,
            "visit_date": _iso(now - timedelta(days=180)),
            "satisfaction": 2.0,
            "venue_spend": benchmarks.PERSONA_V2_SPEND,
            "summary": "Nina's premier visit was disrupted by rain, no covered-seat contingency, and a missed hospitality dinner window.",
            "state": "closed_bad",
        },
        {
            "visit_id": config.VISIT_3_ID,
            "guest_id": config.DEMO_GUEST_ID,
            "event_id": config.DEMO_EVENT_ID,
            "visit_date": _iso(now),
            "satisfaction": None,
            "venue_spend": 0,
            "projected_spend": benchmarks.PERSONA_V3_PROJECTED_INITIAL,
            "summary": "Agent loaded prior event memories. Rain-delay plan proactively protects Mikiko's first-timer path and Nina's premier hospitality experience.",
            "state": "in_progress",
        },
    ]


VISITS: Final[list[dict[str, Any]]] = _build_visits()


VENUE_LOCATIONS: Final[list[dict[str, Any]]] = [
    {
        "location_id": "centre_court",
        "name": "Centre Court",
        "type": "show_court",
        "status": "operational",
        "current_wait_minutes": 18,
        "has_queue_cover": True,
        "accessibility_rating": "excellent",
    },
    {
        "location_id": "court_1",
        "name": "Court 1",
        "type": "show_court",
        "status": "operational",
        "current_wait_minutes": 22,
        "has_queue_cover": True,
        "accessibility_rating": "good",
    },
    {
        "location_id": "court_2",
        "name": "Court 2",
        "type": "outdoor_court",
        "status": "operational",
        "current_wait_minutes": 35,
        "has_queue_cover": False,
        "accessibility_rating": "good",
    },
    {
        "location_id": "covered_practice_court",
        "name": "Covered Practice Court",
        "type": "covered_court",
        "status": "operational",
        "current_wait_minutes": 10,
        "has_queue_cover": True,
        "accessibility_rating": "excellent",
    },
    {
        "location_id": "champions_lounge",
        "name": "Champions Lounge",
        "type": "hospitality",
        "status": "operational",
        "current_wait_minutes": 8,
        "has_queue_cover": True,
        "accessibility_rating": "excellent",
    },
    {
        "location_id": "food_village",
        "name": "Food Village",
        "type": "dining",
        "status": "operational",
        "current_wait_minutes": 12,
        "has_queue_cover": False,
        "accessibility_rating": "good",
    },
]


VENUES: Final[list[dict[str, Any]]] = [
    {
        "venue_id": "venue_summit_cafe",
        "name": "Baseline Cafe",
        "type": "cafe",
        "indoor": True,
        "adjacent_to": ["centre_court", "court_1"],
        "spend_per_party_avg": benchmarks.COURT_SUSPENSION_PER_PARTY_LIFT,
        "daily_projected_revenue": benchmarks.VENUE_DAILY_PROJECTED["venue_summit_cafe"],
    },
    {
        "venue_id": "venue_riverbend_grill",
        "name": "Champions Dining Room",
        "type": "restaurant",
        "indoor": True,
        "adjacent_to": ["champions_lounge", "centre_court"],
        "spend_per_party_avg": benchmarks.STORM_PER_PARTY_LIFT,
        "daily_projected_revenue": benchmarks.VENUE_DAILY_PROJECTED["venue_riverbend_grill"],
    },
    {
        "venue_id": "venue_starlight_lounge",
        "name": "Premier Club Lounge",
        "type": "premium_bar",
        "indoor": True,
        "adjacent_to": ["centre_court"],
        "spend_per_party_avg": 65,
        "daily_projected_revenue": benchmarks.VENUE_DAILY_PROJECTED["venue_starlight_lounge"],
    },
    {
        "venue_id": "venue_canyon_marketplace",
        "name": "Merchandise Hall",
        "type": "merchandise",
        "indoor": False,
        "partial_indoor": True,
        "adjacent_to": ["court_2"],
        "spend_per_party_avg": 42,
        "daily_projected_revenue": benchmarks.VENUE_DAILY_PROJECTED["venue_canyon_marketplace"],
    },
    {
        "venue_id": "venue_emerald_pavilion",
        "name": "Covered Garden Pavilion",
        "type": "dining",
        "indoor": True,
        "adjacent_to": ["covered_practice_court"],
        "spend_per_party_avg": 56,
        "daily_projected_revenue": benchmarks.VENUE_DAILY_PROJECTED["venue_emerald_pavilion"],
    },
    {
        "venue_id": "venue_sunset_terrace",
        "name": "Rooftop Terrace",
        "type": "dining",
        "indoor": False,
        "partial_indoor": True,
        "adjacent_to": ["court_1"],
        "spend_per_party_avg": 72,
        "daily_projected_revenue": benchmarks.VENUE_DAILY_PROJECTED["venue_sunset_terrace"],
    },
    {
        "venue_id": "venue_frost_refresh",
        "name": "Courtside Refresh",
        "type": "snacks",
        "indoor": False,
        "adjacent_to": ["food_village"],
        "spend_per_party_avg": 18,
        "daily_projected_revenue": benchmarks.VENUE_DAILY_PROJECTED["venue_frost_refresh"],
    },
]


INITIAL_EVENT_METRICS: Final[dict[str, Any]] = {
    "event_id": config.DEMO_EVENT_ID,
    "date": datetime.now(timezone.utc).date().isoformat(),
    "wait_minutes_saved": benchmarks.DAILY_WAIT_MINUTES_SAVED,
    "reservations_booked": benchmarks.DAILY_RESERVATIONS_BOOKED,
    "spend_lift_pct": 15.8,
    "churn_risk_prevented": benchmarks.DAILY_CHURN_PREVENTED_TARGET,
    "active_guests": benchmarks.AVG_DAILY_ATTENDANCE,
    "active_parties": benchmarks.DAILY_ACTIVE_PARTIES,
    "agent_actions_today": 38,
    "peak_concurrent": benchmarks.PEAK_HOUR_CONCURRENT,
    "line_skip_adoption": benchmarks.LINE_SKIP_ADOPTION_DEFAULT,
    "wait_share_current": benchmarks.WAIT_SHARE_BASELINE,
    "wait_share_target": benchmarks.WAIT_SHARE_AGENT_TARGET,
}


def get_guest_namespace() -> tuple[str, str]:
    """Return the namespace tuple for the demo guest."""
    return (config.NAMESPACE_GUESTS, config.DEMO_GUEST_ID)


def get_fleet_namespace() -> tuple[str, str]:
    """Return the namespace tuple for the demo operator patterns."""
    return (config.NAMESPACE_FLEET, config.DEMO_EVENT_ID)
