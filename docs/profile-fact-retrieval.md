# Profile-Fact Retrieval Design

## Pattern

**Keyword-triggered join** between semantic memory (vector search) and structured profile lookup (document fetch).

When a user searches "peanut allergy dining options," the system:

1. Recognizes "peanut" and "allergy" as profile-relevant keywords
2. Fetches structured facts from the guest profile (e.g., "Nila has peanut_allergy")
3. Runs vector search across memory namespaces
4. Merges results: profile facts pinned to top, vector results ranked by score

## Why It Matters

This demonstrates a real architectural pattern for AI agents:

- **Semantic memory** (vector search) is great for fuzzy recall — "what happened on past visits?" — but it's probabilistic. A query about peanut allergies might surface relevant memories, or might not if the exact phrasing differs.

- **Structured lookup** (document fetch) is deterministic. Profile flags like `peanut_allergy` are known facts captured at booking time. They should always surface when relevant, regardless of embedding similarity.

The combination ensures the agent never "forgets" critical safety information while still leveraging semantic search for richer context.

## Implementation

### Keyword Mapping (`db.py`)

```python
FLAG_KEYWORD_MAP = {
    "allergy": ["peanut_allergy", "nut_allergy", ...],
    "wheelchair": ["wheelchair_user"],
    "coaster": ["coaster_priority"],
    ...
}
```

When a query contains any mapped keyword, the corresponding flags are considered relevant.

### Profile Lookup (`db.py`)

```python
def lookup_guest_flags(guest_id: str) -> list[dict]:
    """Fetch all profile flags for a guest's party members."""
```

Returns structured entries like:
```python
{
    "member_id": "nila",
    "member_name": "Nila",
    "member_role": "toddler",
    "flag": "peanut_allergy"
}
```

### Endpoint Extension (`server.py`)

The `/api/unified-search` endpoint:
1. Checks `include_profile` parameter (default: true)
2. Calls `flags_for_query(query)` to get relevant flags
3. If flags match, fetches profile entries and filters to relevant ones
4. Formats as `profile_fact` kind with human-readable text
5. Prepends to vector results

Response includes `profile_join_applied: true` when the join fired.

### Frontend (`index.html`)

Profile facts render with:
- Amber PROFILE badge
- No cosine score (displays "—")
- Member role shown as context

## Result Kinds

| Kind | Source | Score | Badge Color |
|------|--------|-------|-------------|
| `profile_fact` | Structured lookup | null | Amber |
| `guest_memory` | Vector search | 0.0–1.0 | Red |
| `fleet_pattern` | Vector search | 0.0–1.0 | Purple |
| `visual_doc` | Vector search | 0.0–1.0 | Green |

## Scope

- **Server-side only**: No agent code changes
- **Flags only**: Does not surface other profile fields (names, ages)
- **Demo guest hardcoded**: Uses `fam_001` for the POC
