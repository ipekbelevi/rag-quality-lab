"""Code-level defenses (Phase 5, extended after the security review). Enabled with GUARDRAIL=on.

A prompt asks the model to behave; code guarantees it. These checks are deterministic,
run outside the model, and keep working even if a model update changes how prompts are followed.

1. check_input:         reject oversized input, known injection phrases and base64-hidden text
                        before any LLM call (zero cost for blocked requests)
2. MAX_ORDER_LOOKUPS:   at most N order lookups per message (stops enumeration in one message)
3. SessionLimiter:      per-session caps on requests, lookups and failed lookups (stops slow enumeration)
4. filter_tool_output:  only allowlisted, business-owned fields reach the model (indirect prompt injection)

SECURITY WARNING: there is still no ownership check on orders. Anyone who knows an order number
gets its details. Before real data, verify ownership (order e-mail, phone digits) and bind lookups
to an authenticated session. See docs/SECURITY_REVIEW.md, finding A1.
"""

import base64
import binascii
import re
from collections import defaultdict

MAX_INPUT_CHARS = 2000  # longest real test question is 157 chars; attacks and cost abuse are much longer
MAX_ORDER_LOOKUPS = 2   # per message

# Per session (an anonymous web visitor). In-memory and single-process: a real deployment
# needs a shared store (Redis) and per-IP limits at the gateway as well.
MAX_REQUESTS_PER_SESSION = 30
MAX_LOOKUPS_PER_SESSION = 10
MAX_FAILED_LOOKUPS_PER_SESSION = 3  # "no such order" x3 -> lookups locked for this session

BLOCKED_MESSAGE = (
    "Sorry, I can't help with that request. I can answer questions about Belevico machines, pods, "
    "orders and policies. For anything else, please contact support@belevico.example."
)
LIMIT_MESSAGE = (
    "You've reached the limit for this conversation. Please contact support@belevico.example "
    "if you need more help."
)

# Phrases that try to override or expose the assistant's instructions
INJECTION_PATTERNS = [
    r"ignore (all |any |the )?(previous|prior|above|earlier|your) (instructions|rules|prompts?)",
    r"disregard (all |any |the )?(previous|prior|above|your) (instructions|rules)",
    r"(reveal|print|show|repeat|output|tell me) (me )?(your|the) (system |initial |hidden )?(prompt|instructions|rules)",
    r"system prompt",
    r"you are now\b",
    r"developer mode",
    r"\bDAN\b",
    r"jailbreak",
    r"system notice to assistant",
    r"new instructions?:",
]
_INJECTION_RE = re.compile("|".join(INJECTION_PATTERNS), re.IGNORECASE)
_BASE64_TOKEN_RE = re.compile(r"[A-Za-z0-9+/]{40,}={0,2}")

# Tool-result fields the model may see: business-owned data only. Customer-written free text
# (gift notes, delivery instructions) is never passed to the model, however it is phrased.
ALLOWED_TOOL_FIELDS = {
    "order_id", "status", "items", "carrier", "tracking_number", "estimated_delivery",
    "delivered_on", "new_estimated_delivery", "reason", "refund_status", "error",
}


def _looks_like_hidden_text(token: str) -> bool:
    """True if a long base64-looking token decodes to readable text (an obfuscated prompt)."""
    try:
        decoded = base64.b64decode(token, validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return False
    printable = sum(ch.isprintable() or ch.isspace() for ch in decoded)
    return len(decoded) > 20 and printable / len(decoded) > 0.9


def check_input(text: str) -> str | None:
    """Return a reason string if the message should be blocked, else None."""
    if len(text) > MAX_INPUT_CHARS:
        return f"input too long ({len(text)} chars, limit {MAX_INPUT_CHARS})"
    if _INJECTION_RE.search(text):
        return "injection phrase"
    if any(_looks_like_hidden_text(t) for t in _BASE64_TOKEN_RE.findall(text)):
        return "base64-encoded text"
    return None


def filter_tool_output(result: dict) -> dict:
    """Keep allowlisted fields only; name the hidden ones so the model can say a note exists."""
    hidden = sorted(k for k in result if k not in ALLOWED_TOOL_FIELDS)
    clean = {k: v for k, v in result.items() if k in ALLOWED_TOOL_FIELDS}
    if hidden:
        clean["hidden_fields"] = hidden
        clean["note"] = "Some fields were hidden for safety and are not available to the assistant."
    return clean


class SessionLimiter:
    """Per-session counters. Sessions without an id are not limited (evals, single CLI calls)."""

    def __init__(self):
        self._requests = defaultdict(int)
        self._lookups = defaultdict(int)
        self._failed = defaultdict(int)

    def allow_request(self, session_id: str | None) -> str | None:
        if session_id is None:
            return None
        self._requests[session_id] += 1
        if self._requests[session_id] > MAX_REQUESTS_PER_SESSION:
            return "session request limit"
        return None

    def allow_lookup(self, session_id: str | None) -> str | None:
        if session_id is None:
            return None
        if self._failed[session_id] >= MAX_FAILED_LOOKUPS_PER_SESSION:
            return "lookups locked after repeated failed order numbers"
        if self._lookups[session_id] >= MAX_LOOKUPS_PER_SESSION:
            return "session lookup limit"
        return None

    def record_lookup(self, session_id: str | None, failed: bool) -> None:
        if session_id is None:
            return
        self._lookups[session_id] += 1
        if failed:
            self._failed[session_id] += 1

    def reset(self) -> None:
        self.__init__()


session_limiter = SessionLimiter()
