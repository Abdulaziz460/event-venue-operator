"""Vercel ASGI entrypoint.

The local app still runs from `event_venue_operator.server`. This file only
adapts that existing FastAPI app to Vercel's Python runtime discovery.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

if not SRC.is_dir():
    raise RuntimeError(f"Expected source directory at {SRC} to import event_venue_operator")

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from event_venue_operator.server import app  # noqa: E402,F401
