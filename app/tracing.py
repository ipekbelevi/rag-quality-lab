"""Thin Langfuse wrapper (Phase 6). Every chatbot request becomes one trace.

- Tracing is ON only when Langfuse keys are set and TRACING != "off". Without keys
  (CI, someone cloning the repo) every call here is a no-op and the app runs unchanged.
- Cost is computed here from our own price table, because a brand-new model may not be
  in Langfuse's price list yet.
- Short-lived scripts must flush before exit, or the last traces are lost (atexit below).
"""

import atexit
import os
from contextlib import nullcontext

from app import config  # noqa: F401  (loads .env before we read the keys)

ENABLED = bool(os.getenv("LANGFUSE_PUBLIC_KEY")) and os.getenv("TRACING", "on") != "off"

# USD per 1M tokens: (input, output)
PRICES = {"claude-haiku-5-5": (0.10, 0.50)}

if ENABLED:
    from langfuse import Langfuse, propagate_attributes
    from langfuse.span_filter import is_langfuse_span

    # The Anthropic SDK emits its own OpenTelemetry spans for every API call. Langfuse picks those
    # up as extra generations, so every LLM call (tokens, cost) was counted twice. Export only
    # our own spans: they also carry the system prompt and our cost calculation.
    _client = Langfuse(should_export_span=is_langfuse_span)
    atexit.register(_client.flush)


class _NoOp:
    """Stands in for a Langfuse observation when tracing is off."""

    def update(self, **kwargs):
        return self


def observe(name: str, as_type: str = "span", **kwargs):
    """Context manager for one step of a trace (span, retriever, generation, tool, ...)."""
    if not ENABLED:
        return nullcontext(_NoOp())
    return _client.start_as_current_observation(name=name, as_type=as_type, **kwargs)


def trace_attributes(**kwargs):
    """Attach tags / session_id / metadata to every observation created inside this block."""
    if not ENABLED:
        return nullcontext()
    return propagate_attributes(**kwargs)


def current_trace_id() -> str | None:
    return _client.get_current_trace_id() if ENABLED else None


def trace_url(trace_id: str) -> str | None:
    return _client.get_trace_url(trace_id=trace_id) if ENABLED else None


def cost(model: str, input_tokens: int, output_tokens: int) -> dict | None:
    if model not in PRICES:
        return None
    price_in, price_out = PRICES[model]
    cost_in, cost_out = input_tokens * price_in / 1e6, output_tokens * price_out / 1e6
    return {"input": cost_in, "output": cost_out, "total": cost_in + cost_out}


def score(trace_id: str, name: str, value: float, comment: str | None = None) -> None:
    """Attach an eval score (e.g. DeepEval Faithfulness) to a trace."""
    if ENABLED and trace_id:
        _client.create_score(trace_id=trace_id, name=name, value=value, comment=comment, data_type="NUMERIC")


def flush() -> None:
    if ENABLED:
        _client.flush()
