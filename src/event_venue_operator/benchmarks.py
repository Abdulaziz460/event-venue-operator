"""
Industry benchmark constants for a fictional flagship-tier event venue.

Numbers calibrated against TEA/AECOM 2024 Global Experience Index, SEC filings
from DIS/CMCSA/FUN/PRKS, IAAPA 2024 Economic Impact Study, and peer-reviewed
research (Dickson/Ford/Laval 2005, Li & Li 2023).

Confidence tiers in comments:
  [H]  = reported by operator or authoritative industry source
  [M]  = derived from reported figures
  [L]  = modeled estimate (flag if pressed on stage)
"""

from __future__ import annotations

from typing import Final

# ---------------------------------------------------------------------------
# Attendance and capacity
# ---------------------------------------------------------------------------

ANNUAL_ATTENDANCE: Final[int] = 12_000_000       # [H] TEA 2024 — mid-tier flagship (between Epcot and Paris)
AVG_DAILY_ATTENDANCE: Final[int] = 33_000        # [M] derived
PEAK_DAY_ATTENDANCE: Final[int] = 80_000         # [M] design-day theory (~2.4x avg)
PEAK_HOUR_CONCURRENT: Final[int] = 55_000        # [M] Little's Law with 8hr dwell, 13hr ops
AVG_DWELL_HOURS: Final[int] = 8                  # [M] TPDB Tokyo Disney

# ---------------------------------------------------------------------------
# Revenue per guest
# ---------------------------------------------------------------------------

AVG_TICKET_PRICE: Final[int] = 150               # [H] flagship midpoint across Disney/Universal
IN_VENUE_PER_CAPITA: Final[int] = 75             # [M] derived from premium venue F&B/merch benchmarks
                                                  #     below implied Disney ~$80-90
TOTAL_PER_CAPITA: Final[int] = AVG_TICKET_PRICE + IN_VENUE_PER_CAPITA  # ~$225

# ---------------------------------------------------------------------------
# Revenue mix
# ---------------------------------------------------------------------------

F_AND_B_SHARE: Final[float] = 0.20               # [M] IAAPA/TEA industry norm
MERCHANDISE_SHARE: Final[float] = 0.13           # [M] industry norm (Disney high end)
PREMIUM_ACCESS_SHARE: Final[float] = 0.08        # [M] derived from Disney Genie+ disclosures

# ---------------------------------------------------------------------------
# Line-skip / premium access
# ---------------------------------------------------------------------------

LINE_SKIP_BASIC_PRICE: Final[int] = 30           # [H] Disney LLMP midpoint 2025-2026
LINE_SKIP_ADOPTION_PEAK: Final[float] = 0.45     # [H] Disney-disclosed (Chapek 2022)
LINE_SKIP_ADOPTION_OFFPEAK: Final[float] = 0.33  # [H] Disney-disclosed
LINE_SKIP_ADOPTION_DEFAULT: Final[float] = 0.40  # [M] midpoint for "busy but not peak" day

# ---------------------------------------------------------------------------
# Wait time economics
# ---------------------------------------------------------------------------

WAIT_SHARE_BASELINE: Final[float] = 0.52         # [H] Li & Li 2023 peer-reviewed
WAIT_SHARE_AGENT_TARGET: Final[float] = 0.38     # [L] modeled target under agent
ATTRACTION_SHARE_BASELINE: Final[float] = 0.20   # [H] Li & Li 2023
PER_CAP_LIFT_FROM_WAIT_REDUCTION: Final[float] = 0.22  # [M] Botrista vendor case study

# ---------------------------------------------------------------------------
# Daily venue revenue projections
# ---------------------------------------------------------------------------
# For a flagship venue doing ~$1.2B annual revenue (12M visitors × $100 per cap):
# F&B annual = $240M → avg ~$660K/day
# Merch annual = $156M → avg ~$430K/day
# Split across 7 venues proportional to type and adjacency:

VENUE_DAILY_PROJECTED: Final[dict[str, int]] = {
    "venue_summit_cafe": 18_500,        # QS, flagship-adjacent
    "venue_riverbend_grill": 42_000,    # TS, large capacity
    "venue_starlight_lounge": 28_000,   # Premium bar
    "venue_canyon_marketplace": 16_000,  # Merch, partial indoor
    "venue_emerald_pavilion": 31_000,   # Dining
    "venue_sunset_terrace": 24_000,     # Dining, partial indoor
    "venue_frost_refresh": 6_500,       # Snack cart
}
# Total daily projected = ~$166K (one cluster of 7 venues at this scale)

# ---------------------------------------------------------------------------
# Event-scale deltas (operator aggregate)
# ---------------------------------------------------------------------------
# When an event happens, how many parties are affected and what's the per-party delta?

COURT_SUSPENSION_AFFECTED_PARTIES: Final[int] = 150   # [L] 150 parties redirected from an outdoor court
COURT_SUSPENSION_PER_PARTY_LIFT: Final[int] = 28      # [L] avg cafe spend after covered reroute
COURT_SUSPENSION_AGGREGATE_LIFT: Final[int] = (
    COURT_SUSPENSION_AFFECTED_PARTIES * COURT_SUSPENSION_PER_PARTY_LIFT
)
# = $4,200 aggregate cafe capture

STORM_AFFECTED_PARTIES: Final[int] = 420            # [L] ~420 parties displaced from outdoor venues
STORM_PER_PARTY_LIFT: Final[int] = 84               # [L] avg hospitality dinner spend
STORM_AGGREGATE_LIFT: Final[int] = STORM_AFFECTED_PARTIES * STORM_PER_PARTY_LIFT
# = $35,280 aggregate hospitality capture

# ---------------------------------------------------------------------------
# Operator framing daily targets (full-day aggregate)
# ---------------------------------------------------------------------------
# These are what the KPI tiles tick toward by end of close-visit:

DAILY_REVENUE_CAPTURE_TARGET: Final[int] = 680_000  # [L] aggregate in-venue revenue influenced by agent
DAILY_CHURN_PREVENTED_TARGET: Final[int] = 140      # [L] high-risk parties diverted to good outcomes
DAILY_REPUTATION_SCORE: Final[float] = 4.6          # [L] avg satisfaction rating protected
DAILY_RESERVATIONS_BOOKED: Final[int] = 620         # [M] derived: ~10K total venue reservations, agent books ~6%
DAILY_WAIT_MINUTES_SAVED: Final[int] = 47_200       # [M] ~0.22hr × 33K guests × 60min reduction
DAILY_ACTIVE_PARTIES: Final[int] = 14_800           # [M] derived from 33K guests / 2.2 avg party size

# ---------------------------------------------------------------------------
# Demo-party single event scale
# ---------------------------------------------------------------------------
# V1 was first-timer friction, V2 was rain-delay hospitality miss,
# V3 is agent-uplifted.

PERSONA_V1_SPEND: Final[int] = 185       # [M] bad day: entered premium-intent, left after lunch
PERSONA_V2_SPEND: Final[int] = 127       # [M] worse day: storm cut visit short before dinner
PERSONA_V3_PROJECTED_INITIAL: Final[int] = 680    # [M] agent morning plan: moderate-premium day
PERSONA_V3_PROJECTED_AFTER_COURT_DELAY: Final[int] = 745   # [M] +$65 covered-route cafe redirect
PERSONA_V3_PROJECTED_AFTER_STORM: Final[int] = 920      # [M] +$175 hospitality dinner + rain recovery
PERSONA_V3_CAPTURED_CLOSE: Final[int] = 1_080           # [M] final: premium-day upside

# Demo-party deltas (what this one party captures at each trigger)
PERSONA_COURT_REDIRECT_DELTA: Final[int] = 65   # [M] QS lunch + merch impulse
PERSONA_STORM_BOOKING_DELTA: Final[int] = 175   # [M] TS dinner + afternoon recovery

# ---------------------------------------------------------------------------
# Problem framing numbers (for the $70B context)
# ---------------------------------------------------------------------------

INDUSTRY_GLOBAL_SIZE_BILLIONS: Final[int] = 70   # [M] 2025 global location-based entertainment, modeled range
INDUSTRY_US_SIZE_BILLIONS: Final[int] = 33       # [H] IBISWorld 2025

# ---------------------------------------------------------------------------
# Fleet memory scale-up factors
# ---------------------------------------------------------------------------
# For rescaling fleet memory incident counts to flagship operations

FLEET_REDIRECT_INCIDENTS: Final[int] = 12_400    # [L] 12M annual / ~1000 = ~12K court-delay incidents
FLEET_WEATHER_EVENTS: Final[int] = 3_800         # [L] 10 years × 380 avg weather-affected days
