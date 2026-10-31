"""Code-level defenses (Phase 5). Enabled with GUARDRAIL=on.

A prompt asks the model to behave; code guarantees it. These checks are deterministic,
run outside the model, and keep working even if a model update changes how prompts are followed.

1. check_input:          block known injection phrases and base64-hidden text before any LLM call
2. MAX_ORDER_LOOKUPS:     at most N order lookups per message (stops enumeration)
3. sanitize_tool_output: remove instruction-like text from tool results (indirect prompt injection)
"""

import base64
import binascii
import re

MAX_ORDER_LOOKUPS = 2

BLOCKED_MESSAGE = (
    "Sorry, I can't help with that request. I can answer questions about Belevico machines, pods, "
    "orders and policies. For anything else, please contact support@belevico.example."
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
    if _INJECTION_RE.search(text):
        return "injection phrase"
    if any(_looks_like_hidden_text(t) for t in _BASE64_TOKEN_RE.findall(text)):
        return "base64-encoded text"
    return None


def sanitize_tool_output(result: dict) -> dict:
    """Replace free-text fields that contain instruction-like text before the model sees them."""
    clean = dict(result)
    for key, value in result.items():
        if isinstance(value, str) and _INJECTION_RE.search(value):
            clean[key] = "[removed by safety filter: this field contained instructions aimed at the assistant]"
    return clean
