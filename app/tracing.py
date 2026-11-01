"""Thin Langfuse wrapper (Phase 6). Every chatbot request becomes one trace.

- Tracing is ON only when Langfuse keys are set and TRACING != "off". Without keys
  (CI, someone cloning the repo) every call here is a no-op and the app runs unchanged.
- PII masking: e-mail addresses, phone numbers and card-like digit runs are replaced before
  anything leaves the process (TRACE_MASK_PII=off disables it; keep it on with real users).
- Cost is computed here from our own price table, because a brand-new model may not be
  in Langfuse's price list yet.
- Short-lived scripts must flush before exit, or the last traces are lost (atexit below).

PRIVACY WARNING: traces contain the user's question, the retrieved chunks and the answer and are
sent to Langfuse Cloud (EU). Masking reduces, but does not remove, personal data. Before real
traffic: data-retention settings and a DPA with the provider (docs/SECURITY_REVIEW.md, section 5).
"""

import atexit
import os
import re
from contextlib import nullcontext

from app import config  # noqa: F401  (loads .env before we read the keys)

ENABLED = bool(os.getenv("LANGFUSE_PUBLIC_KEY")) and os.getenv("TRACING", "on") != "off"
MASK_PII = os.getenv("TRACE_MASK_PII", "on") != "off"

# USD per 1M tokens: (input, output)
PRICES = {"claude-haiku-5-5": (0.10, 0.50)}

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_CARD_RE = re.compile(r"\b\d(?:[ -]?\d){12,18}\b")                 # 13-19 digits with optional spaces/dashes
_PHONE_RE = re.compile(r"(?<!\w)\+?\d[\d ()-]{8,}\d(?!\w)")        # 10+ digits with separators, e.g. 0850 555 23 58


def mask_pii(data):
    """Recursively replace e-mails, card-like numbers and phone numbers in strings."""
    if isinstance(data, str):
        data = _EMAIL_RE.sub("[EMAIL]", data)
        data = _CARD_RE.sub("[CARD]", data)
        return _PHONE_RE.sub("[PHONE]", data)
    if isinstance(data, dict):
        return {k: mask_pii(v) for k, v in data.items()}
    if isinstance(data, (list, tuple)):
        return [mask_pii(v) for v in data]
    return data


if ENABLED:
    from langfuse import Langfuse, propagate_attributes
    from langfuse.span_filter import is_langfuse_span

    # The Anthropic SDK emits its own OpenTelemetry spans for every API call. Langfuse picks those
    # up as extra generations, so every LLM call (tokens, cost) was counted twice. Export only
    # our own spans: they also carry the system prompt and our cost calculation.
    _client = Langfuse(should_export_span=is_langfuse_span, mask=mask_pii if MASK_PII else None)
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
    return propagate_attributes(**{k: v for k, v in kwargs.items() if v is not None})


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
