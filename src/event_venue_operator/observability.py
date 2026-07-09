"""Optional Langfuse observability helpers."""

from __future__ import annotations

import logging
from contextlib import contextmanager, nullcontext
from typing import Any, Iterator

from langfuse import Langfuse

from . import config

log = logging.getLogger("tpo.observability")

_client: Langfuse | None = None


def enabled() -> bool:
    """Return whether Langfuse tracing is configured."""
    return config.LANGFUSE_ENABLED


def get_client() -> Langfuse | None:
    """Return a lazily initialized Langfuse client, if configured."""
    global _client
    if not enabled():
        return None
    if _client is None:
        _client = Langfuse(
            public_key=config.LANGFUSE_PUBLIC_KEY,
            secret_key=config.LANGFUSE_SECRET_KEY,
            host=config.LANGFUSE_HOST,
        )
    return _client


@contextmanager
def trace(
    name: str,
    *,
    input: Any | None = None,
    metadata: dict[str, Any] | None = None,
    as_type: str = "span",
) -> Iterator[Any | None]:
    """Create a Langfuse observation when configured; otherwise no-op."""
    client = get_client()
    if client is None:
        with nullcontext(None) as observation:
            yield observation
        return

    try:
        observation_context = client.start_as_current_observation(
            name=name,
            as_type=as_type,
            input=input,
            metadata=metadata,
        )
    except Exception:
        log.exception("Langfuse observation setup failed: %s", name)
        with nullcontext(None) as observation:
            yield observation
        return

    with observation_context as observation:
        yield observation


def update(output: Any | None = None, metadata: dict[str, Any] | None = None) -> None:
    """Update the current Langfuse span if tracing is enabled."""
    client = get_client()
    if client is None:
        return
    try:
        client.update_current_span(output=output, metadata=metadata)
    except Exception:
        log.exception("Langfuse span update failed")


def flush() -> None:
    """Flush buffered Langfuse events when tracing is enabled."""
    client = get_client()
    if client is None:
        return
    try:
        client.flush()
    except Exception:
        log.exception("Langfuse flush failed")
